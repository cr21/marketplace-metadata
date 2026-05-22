"""Data catalog crawler.

Entry point: crawl_dataset(). Joins four INFORMATION_SCHEMA queries in Python
to produce CatalogRows, then optionally enriches them via the LLM enricher.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog
from google.cloud import bigquery

from catalog_agent.bq.information_schema import (
    BQColumnInfo,
    BQRoutineInfo,
    BQTableInfo,
    get_table_options,
    list_columns,
    list_routines,
    list_tables,
)
from catalog_agent.catalog.llm_enricher import enrich_catalog_row
from catalog_agent.catalog.models import CatalogRow, ColumnRecord
from catalog_agent.catalog.pii import is_pii

if TYPE_CHECKING:
    from openai import OpenAI

logger = structlog.get_logger(__name__)

# Maps INFORMATION_SCHEMA.TABLES.table_type to catalog asset_type values.
_TABLE_TYPE_MAP: dict[str, str] = {
    "BASE TABLE": "TABLE",
    "VIEW": "VIEW",
    "MATERIALIZED VIEW": "MATERIALIZED_VIEW",
    "EXTERNAL": "EXTERNAL",
    "SNAPSHOT": "TABLE",
    "CLONE": "TABLE",
}


def _map_asset_type(table_type: str) -> str:
    return _TABLE_TYPE_MAP.get(table_type.upper(), "TABLE")


def _build_column_map(columns: list[BQColumnInfo]) -> dict[str, list[BQColumnInfo]]:
    """Group columns by table_name preserving ordinal_position order."""
    col_map: dict[str, list[BQColumnInfo]] = defaultdict(list)
    for col in columns:
        col_map[col.table_name].append(col)
    return dict(col_map)


def _build_table_metadata(
    table: BQTableInfo,
    options: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the table_metadata JSON dict from INFORMATION_SCHEMA sources."""
    partitioning: dict[str, Any] = {}
    if table.time_partitioning_type:
        partitioning = {
            "type": table.time_partitioning_type,
            "field": table.time_partitioning_field,
            "expiration_ms": table.time_partitioning_expiration_ms,
        }
    elif table.range_partitioning_field:
        partitioning = {
            "type": "RANGE",
            "field": table.range_partitioning_field,
        }

    return {
        "description": options.get("description", ""),
        "labels": options.get("labels", {}),
        "row_count": table.row_count,
        "size_bytes": table.size_bytes,
        "created": table.creation_time.isoformat() if table.creation_time else None,
        "modified": table.last_modified_time.isoformat() if table.last_modified_time else None,
        "clustering_fields": table.clustering_fields,
        "partitioning": partitioning,
    }


def _build_routine_metadata(routine: BQRoutineInfo) -> dict[str, Any]:
    return {
        "description": "",
        "routine_type": routine.routine_type,
        "routine_definition": routine.routine_definition or "",
    }


def crawl_dataset(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    openai_client: OpenAI | None = None,
    openai_model: str = "gpt-4o-mini",
) -> list[CatalogRow]:
    """Crawl a BigQuery dataset and return one CatalogRow per asset.

    Queries four INFORMATION_SCHEMA views in sequence, assembles rows in Python,
    then optionally enriches descriptions and PII flags via OpenAI when
    openai_client is provided.

    Args:
        client: Authenticated BigQuery client.
        project_id: GCP project to crawl.
        dataset_id: Dataset to crawl.
        openai_client: Optional OpenAI client for LLM enrichment. When None,
            PII is determined by the heuristic tagger only and descriptions are
            left as whatever INFORMATION_SCHEMA contains.
        openai_model: OpenAI model for enrichment (default: gpt-4o-mini).

    Returns:
        A list of CatalogRows — one per table, view, and routine.
    """
    log = logger.bind(project_id=project_id, dataset_id=dataset_id)
    log.info("crawl_dataset_start")

    tables = list_tables(client, project_id, dataset_id)
    columns = list_columns(client, project_id, dataset_id)
    routines = list_routines(client, project_id, dataset_id)
    options_map = get_table_options(client, project_id, dataset_id)

    col_map = _build_column_map(columns)

    rows: list[CatalogRow] = []

    for table in tables:
        asset_type = _map_asset_type(table.table_type)
        table_opts = options_map.get(table.table_name, {})
        metadata = _build_table_metadata(table, table_opts)

        raw_cols = col_map.get(table.table_name, [])
        col_records = [
            ColumnRecord(
                name=col.column_name,
                data_type=col.data_type,
                description=col.description or "",
                is_pii=is_pii(col.column_name, col.data_type),
            )
            for col in raw_cols
        ]

        rows.append(
            CatalogRow(
                project_id=project_id,
                dataset_id=dataset_id,
                asset=table.table_name,
                asset_type=asset_type,
                table_metadata=metadata,
                columns=col_records,
            )
        )

    for routine in routines:
        rows.append(
            CatalogRow(
                project_id=project_id,
                dataset_id=dataset_id,
                asset=routine.routine_name,
                asset_type="ROUTINE",
                table_metadata=_build_routine_metadata(routine),
                columns=[],
            )
        )

    log.info("crawl_dataset_raw", asset_count=len(rows))

    if openai_client is not None:
        rows = [enrich_catalog_row(row, openai_client, openai_model) for row in rows]
        log.info("crawl_dataset_enriched")

    log.info("crawl_dataset_done", asset_count=len(rows))
    return rows
