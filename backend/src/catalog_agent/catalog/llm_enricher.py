"""OpenAI-based enrichment for catalog rows.

Enriches CatalogRows by generating descriptions and PII flags for:
- Columns whose description is empty in INFORMATION_SCHEMA
- Tables/views whose description is empty in TABLE_OPTIONS

One batched OpenAI call is made per asset (all missing-description columns
bundled into a single prompt). If OpenAI is unavailable or the call fails,
the original row is returned unchanged — the crawl never fails due to LLM errors.
"""

import json
import re
from typing import TYPE_CHECKING, Any

import structlog

from catalog_agent.catalog.models import CatalogRow, ColumnRecord

if TYPE_CHECKING:
    from openai import OpenAI

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a data catalog assistant that generates concise metadata for BigQuery assets.
Always respond with valid JSON matching the requested schema exactly.
Rules for every description field:
- One sentence, under 20 words.
- Start directly with what the data IS or DOES — never with "This table", "This view", "This column", "Contains", "Stores", or "Holds".
- Use a noun phrase or verb phrase: e.g. "Monthly revenue aggregated by region and product category."
"""

_USER_PROMPT_TEMPLATE = """\
Generate metadata for the following BigQuery {asset_type} named "{asset}" in dataset "{dataset_id}".

{table_desc_instruction}

Columns needing description (provide description, is_pii flag, and pii_rationale for each):
{columns_json}

Return JSON with this exact structure:
{{
  {table_desc_field}
  "columns": [
    {{
      "name": "<column_name>",
      "description": "<noun or verb phrase — no 'This column/table/view' prefix>",
      "is_pii": <true|false>,
      "pii_rationale": "<brief reason if is_pii is true, empty string otherwise>"
    }}
  ]
}}
"""


def _build_prompt(
    row: CatalogRow,
    columns_to_enrich: list[ColumnRecord],
    need_table_description: bool,
) -> str:
    """Build the user prompt for a single asset."""
    table_desc_instruction = (
        'Also generate a one-sentence "table_description" '
        if need_table_description
        else ""
    )
    table_desc_field = (
        '"table_description": "<one sentence description>",'
        if need_table_description
        else ""
    )
    columns_json = json.dumps(
        [{"name": col.name, "data_type": col.data_type} for col in columns_to_enrich],
        indent=2,
    )
    return _USER_PROMPT_TEMPLATE.format(
        asset_type=row.asset_type,
        asset=row.asset,
        dataset_id=row.dataset_id,
        table_desc_instruction=table_desc_instruction,
        columns_json=columns_json,
        table_desc_field=table_desc_field,
    )


_STRIP_PREFIX = re.compile(
    r"^(this\s+(table|view|column|dataset)\s+(contains|stores|holds|has|represents|is)\s*[:\-]?\s*)",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    """Strip common LLM filler prefixes and capitalise the first letter."""
    text = _STRIP_PREFIX.sub("", text).strip()
    return text[:1].upper() + text[1:] if text else text


def _apply_enrichment(
    row: CatalogRow,
    result: dict[str, Any],
    columns_to_enrich: list[ColumnRecord],
    need_table_description: bool,
) -> CatalogRow:
    """Apply LLM result to the CatalogRow, returning an updated copy."""
    enriched_columns = list(row.columns)
    name_to_result: dict[str, dict[str, Any]] = {c["name"]: c for c in result.get("columns", [])}

    for i, col in enumerate(enriched_columns):
        if col.name in name_to_result:
            llm_col = name_to_result[col.name]
            enriched_columns[i] = ColumnRecord(
                name=col.name,
                data_type=col.data_type,
                description=_clean(str(llm_col.get("description", col.description) or "")),
                is_pii=bool(llm_col.get("is_pii", col.is_pii)),
            )

    updated_metadata = dict(row.table_metadata)
    if need_table_description and result.get("table_description"):
        updated_metadata["description"] = _clean(str(result["table_description"]))

    # Collect pii_rationale for any flagged columns
    rationale: dict[str, str] = {}
    for col_result in result.get("columns", []):
        if col_result.get("is_pii") and col_result.get("pii_rationale"):
            rationale[col_result["name"]] = str(col_result["pii_rationale"])
    if rationale:
        existing = updated_metadata.get("pii_rationale", {})
        if isinstance(existing, dict):
            existing.update(rationale)
            updated_metadata["pii_rationale"] = existing
        else:
            updated_metadata["pii_rationale"] = rationale

    return CatalogRow(
        project_id=row.project_id,
        dataset_id=row.dataset_id,
        asset=row.asset,
        asset_type=row.asset_type,
        table_metadata=updated_metadata,
        columns=enriched_columns,
    )


def enrich_catalog_row(row: CatalogRow, client: "OpenAI", model: str) -> CatalogRow:
    """Enrich a single CatalogRow with LLM-generated descriptions and PII flags.

    Only calls the LLM when there is work to do (missing descriptions). Returns the
    original row unchanged on any error so the crawl is never blocked by LLM failures.

    Args:
        row: The CatalogRow to enrich.
        client: An authenticated OpenAI client.
        model: The OpenAI model to use (e.g. "gpt-4o-mini").

    Returns:
        An enriched CatalogRow (or the original if nothing needed enrichment / call failed).
    """
    columns_to_enrich = [col for col in row.columns if not col.description]
    need_table_description = not row.table_metadata.get("description")

    if not columns_to_enrich and not need_table_description:
        return row

    log = logger.bind(
        asset=row.asset,
        dataset=row.dataset_id,
        columns_to_enrich=len(columns_to_enrich),
        need_table_description=need_table_description,
    )

    try:
        prompt = _build_prompt(row, columns_to_enrich, need_table_description)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        result: dict[str, Any] = json.loads(raw)
        log.info("llm_enrichment_complete")
        return _apply_enrichment(row, result, columns_to_enrich, need_table_description)
    except Exception:
        log.warning("llm_enrichment_failed", exc_info=True)
        return row
