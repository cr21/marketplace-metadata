"""Idempotent writer for data_catalog_registry.

merge_catalog_rows() issues a single parameterized BQ MERGE statement keyed on
(project_id, dataset_id, asset). Re-running on unchanged data yields 0 inserts
and 0 updates — the MERGE condition compares both table_metadata and the columns
JSON so it only fires an UPDATE when something actually changed.
"""

import json

import structlog
from google.cloud import bigquery

from catalog_agent.catalog.models import CatalogRow, MergeResult

logger = structlog.get_logger(__name__)

# The MERGE target is always the catalog registry table, not the source project.
_DEFAULT_TABLE = "data_catalog_registry"

_MERGE_SQL = """
MERGE `{catalog_project}.{catalog_dataset}.{table_id}` AS target
USING (
  SELECT
    JSON_VALUE(row_data, '$.project_id')  AS project_id,
    JSON_VALUE(row_data, '$.dataset_id')  AS dataset_id,
    JSON_VALUE(row_data, '$.asset')        AS asset,
    JSON_VALUE(row_data, '$.asset_type')   AS asset_type,
    JSON_VALUE(row_data, '$.table_metadata') AS table_metadata,
    ARRAY(
      SELECT AS STRUCT
        JSON_VALUE(col, '$.name')                  AS name,
        JSON_VALUE(col, '$.data_type')             AS data_type,
        JSON_VALUE(col, '$.description')           AS description,
        CAST(JSON_VALUE(col, '$.is_pii') AS BOOL)  AS is_pii
      FROM UNNEST(JSON_QUERY_ARRAY(row_data, '$.columns')) AS col
    ) AS columns
  FROM UNNEST(JSON_QUERY_ARRAY(@rows_json)) AS row_data
) AS source
ON  target.project_id  = source.project_id
AND target.dataset_id  = source.dataset_id
AND target.asset       = source.asset
WHEN MATCHED AND (
  target.table_metadata != source.table_metadata
  OR TO_JSON_STRING(target.columns) != TO_JSON_STRING(source.columns)
) THEN UPDATE SET
  asset_type     = source.asset_type,
  table_metadata = source.table_metadata,
  columns        = source.columns
WHEN NOT MATCHED THEN INSERT
  (project_id, dataset_id, asset, asset_type, table_metadata, columns)
VALUES
  (source.project_id, source.dataset_id, source.asset,
   source.asset_type, source.table_metadata, source.columns)
"""


def merge_catalog_rows(
    client: bigquery.Client,
    rows: list[CatalogRow],
    catalog_project_id: str,
    catalog_dataset_id: str,
    table_id: str = _DEFAULT_TABLE,
) -> MergeResult:
    """MERGE a list of CatalogRows into the registry table using a single BQ call.

    The MERGE key is (project_id, dataset_id, asset). Rows are passed as a JSON
    string query parameter (one BQ call per invocation regardless of row count).

    Args:
        client: Authenticated BigQuery client.
        rows: Rows to merge. Empty list → returns 0/0/0 immediately.
        catalog_project_id: GCP project that hosts the catalog_registry dataset.
        catalog_dataset_id: Dataset name (e.g. "catalog_registry").
        table_id: Target table name (default: "data_catalog_registry").

    Returns:
        MergeResult with inserted / updated / unchanged counts.
    """
    if not rows:
        return MergeResult(inserted=0, updated=0, unchanged=0)

    rows_json = json.dumps([r.to_bq_dict() for r in rows])

    sql = _MERGE_SQL.format(
        catalog_project=catalog_project_id,
        catalog_dataset=catalog_dataset_id,
        table_id=table_id,
    )

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("rows_json", "STRING", rows_json),
        ]
    )

    logger.info(
        "merge_catalog_rows_start",
        catalog_project=catalog_project_id,
        catalog_dataset=catalog_dataset_id,
        row_count=len(rows),
    )

    job = client.query(sql, job_config=job_config)
    job.result()  # wait for completion; raises on error

    inserted = 0
    updated = 0
    if job.dml_stats:
        inserted = job.dml_stats.inserted_row_count or 0
        updated = job.dml_stats.updated_row_count or 0
    unchanged = max(0, len(rows) - inserted - updated)

    logger.info(
        "merge_catalog_rows_done",
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
    )
    return MergeResult(inserted=inserted, updated=updated, unchanged=unchanged)
