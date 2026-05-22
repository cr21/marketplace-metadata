# M01 — Data Catalog Crawler

## Overview

The crawler queries four `INFORMATION_SCHEMA` views for a given `(project_id, dataset_id)` and produces one `CatalogRow` per table, view, or routine. Rows are written to `catalog_registry.data_catalog_registry` using a single parameterized `MERGE` call (idempotent).

When `OPENAI_API_KEY` is set, the crawler also calls OpenAI to generate descriptions and PII flags for any column or table that has no description in `INFORMATION_SCHEMA`.

---

## Files

| File | Purpose |
|------|---------|
| `backend/src/catalog_agent/catalog/models.py` | `ColumnRecord`, `CatalogRow`, `MergeResult` Pydantic models |
| `backend/src/catalog_agent/catalog/pii.py` | Heuristic PII tagger |
| `backend/src/catalog_agent/catalog/llm_enricher.py` | OpenAI enrichment for missing descriptions |
| `backend/src/catalog_agent/catalog/crawler.py` | `crawl_dataset()` — assembles rows from IS queries |
| `backend/src/catalog_agent/catalog/__main__.py` | CLI entry (`python -m catalog_agent.catalog`) |
| `backend/src/catalog_agent/bq/information_schema.py` | IS query functions |
| `backend/src/catalog_agent/bq/writer.py` | `merge_catalog_rows()` — BQ MERGE writer |
| `infra/bq/data_catalog_registry.sql` | DDL reference (table already exists) |

---

## Running the crawler

```bash
# From repo root — using Makefile:
make demo-m01 PROJECT=my-project DATASET=my_dataset

# Or directly:
cd backend
uv run python -m catalog_agent.catalog --project=my-project --dataset=my_dataset

# Dry run (no BQ write):
uv run python -m catalog_agent.catalog --project=my-project --dataset=my_dataset --dry-run
```

---

## PII heuristic patterns

The following patterns are checked **case-insensitively** against the column name. A match anywhere in the name triggers `is_pii=True`.

| Pattern | Example columns flagged |
|---------|------------------------|
| `email` | `email`, `email_address`, `user_email` |
| `phone` | `phone`, `phone_number` |
| `mobile` | `mobile`, `mobile_number` |
| `ssn` | `ssn`, `social_security_number` |
| `social_security` | `social_security_number` |
| `\bdob\b` | `dob` (exact word boundary) |
| `date_of_birth` | `date_of_birth` |
| `birth_date` | `birth_date` |
| `birthday` | `birthday` |
| `first_name` | `first_name` |
| `last_name` | `last_name` |
| `full_name` | `full_name` |
| `display_name` | `display_name` |
| `person_name` | `person_name` |
| `customer_name` | `customer_name` |
| `contact_name` | `contact_name` |
| `user_name` | `user_name` |
| `address` | `address`, `home_address`, `street_address` |
| `postal_code` | `postal_code` |
| `zip_code` | `zip_code` |
| `\bzip\b` | `zip` (exact word boundary) |
| `\bstreet\b` | `street` |
| `credit_card` | `credit_card` |
| `card_number` | `card_number` |
| `card_num` | `card_num` |
| `\bcvv\b` | `cvv` |
| `\bcvc\b` | `cvc` |
| `account_number` | `account_number` |
| `passport` | `passport`, `passport_number` |
| `tax_id` | `tax_id` |
| `\btin\b` | `tin` |
| `\bnin\b` | `nin` |
| `national_id` | `national_id` |
| `drivers_licen` | `drivers_license`, `drivers_licence` |
| `license_number` | `license_number` |
| `ip_address` | `ip_address` |
| `ip_addr` | `ip_addr` |
| `\bgender\b` | `gender` |
| `ethnicity` | `ethnicity` |
| `\brace\b` | `race` |
| `\bsalary\b` | `salary` |
| `\bincome\b` | `income` |
| `biometric` | `biometric` |
| `fingerprint` | `fingerprint` |

**Not flagged:** `id`, `user_id`, `order_id`, `created_at`, `updated_at`, `amount`, `quantity`, `status`, `table_name`, `column_name`, `file_name`, `description`, `category`, `region`, `country_code`.

---

## LLM enrichment

When `OPENAI_API_KEY` is set, the crawler calls OpenAI for each asset where:
- Any column has an empty `description` in `INFORMATION_SCHEMA`, **or**
- The table/view has no `description` in `TABLE_OPTIONS`

All missing-description columns for one asset are batched into a single prompt. The response provides:
- A one-sentence table/view description (stored in `table_metadata.description`)
- For each column: `description`, `is_pii` (overrides heuristic), `pii_rationale`
- `pii_rationale` values are stored in `table_metadata.pii_rationale.<column_name>`

If the OpenAI call fails for any reason, the original row is returned unchanged. The crawl never fails due to LLM errors.

Columns that already have descriptions in BQ are **not** sent to the LLM and use the heuristic for `is_pii`.

---

## MERGE SQL

The writer issues a single parameterized `MERGE` with the entire row set passed as a JSON string in `@rows_json`:

```sql
MERGE `{catalog_project}.{catalog_dataset}.data_catalog_registry` AS target
USING (
  SELECT
    JSON_VALUE(row_data, '$.project_id')      AS project_id,
    JSON_VALUE(row_data, '$.dataset_id')      AS dataset_id,
    JSON_VALUE(row_data, '$.asset')           AS asset,
    JSON_VALUE(row_data, '$.asset_type')      AS asset_type,
    JSON_VALUE(row_data, '$.table_metadata')  AS table_metadata,
    ARRAY(
      SELECT AS STRUCT
        JSON_VALUE(col, '$.name')                 AS name,
        JSON_VALUE(col, '$.data_type')            AS data_type,
        JSON_VALUE(col, '$.description')          AS description,
        CAST(JSON_VALUE(col, '$.is_pii') AS BOOL) AS is_pii
      FROM UNNEST(JSON_QUERY_ARRAY(row_data, '$.columns')) AS col
    ) AS columns
  FROM UNNEST(JSON_QUERY_ARRAY(@rows_json)) AS row_data
) AS source
ON  target.project_id = source.project_id
AND target.dataset_id = source.dataset_id
AND target.asset      = source.asset
WHEN MATCHED AND (
  target.table_metadata != source.table_metadata
  OR TO_JSON_STRING(target.columns) != TO_JSON_STRING(source.columns)
) THEN UPDATE SET
  asset_type     = source.asset_type,
  table_metadata = source.table_metadata,
  columns        = source.columns
WHEN NOT MATCHED THEN INSERT (project_id, dataset_id, asset, asset_type, table_metadata, columns)
VALUES (source.project_id, source.dataset_id, source.asset,
        source.asset_type, source.table_metadata, source.columns)
```

**Idempotency mechanism:**
- `table_metadata` is serialized with `json.dumps(sort_keys=True)` so the string is byte-identical across runs.
- Columns are ordered by `ordinal_position` from `INFORMATION_SCHEMA.COLUMNS`, ensuring consistent JSON.
- A second run on unchanged data finds no `!=` differences → no `UPDATE` → `inserted=0, updated=0`.

---

## Example output

```
Crawling my-project.sales ...
Found 8 assets: 5 tables, 2 views, 1 routines. 3 PII columns detected.
Merge complete — inserted: 8, updated: 0, unchanged: 0

# Second run (unchanged data):
Merge complete — inserted: 0, updated: 0, unchanged: 8
```

---

## `table_metadata` JSON shape

```json
{
  "description": "Orders placed by customers",
  "labels": {"env": "prod", "team": "commerce"},
  "row_count": 1234567,
  "size_bytes": 98765432,
  "created": "2023-01-15T10:00:00+00:00",
  "modified": "2024-03-20T14:32:11+00:00",
  "clustering_fields": ["customer_id"],
  "partitioning": {
    "type": "DAY",
    "field": "order_date",
    "expiration_ms": null
  },
  "pii_rationale": {
    "email": "Email is a personal identifier",
    "phone_number": "Phone numbers identify individuals"
  }
}
```

For routines, `table_metadata` contains only:
```json
{
  "description": "",
  "routine_type": "PROCEDURE",
  "routine_definition": "BEGIN ... END"
}
```
