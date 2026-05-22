"""Idempotent writer for lineage_registry.

merge_lineage_edges() issues a single parameterized BQ MERGE statement keyed on
(project_id, dataset_id, asset, direction, source_fqn, target_fqn,
 source_column, target_column, lineage_source).
NULL values in the key are handled via IS NOT DISTINCT FROM so two NULL-column
edges don't falsely match a non-NULL edge.
"""

import json

import structlog
from google.cloud import bigquery

from catalog_agent.lineage.models import LineageEdge, LineageReport

logger = structlog.get_logger(__name__)

_DEFAULT_TABLE = "lineage_registry"

_MERGE_SQL = """
MERGE `{catalog_project}.{catalog_dataset}.{table_id}` AS target
USING (
  SELECT
    JSON_VALUE(row_data, '$.project_id')    AS project_id,
    JSON_VALUE(row_data, '$.dataset_id')    AS dataset_id,
    JSON_VALUE(row_data, '$.asset')          AS asset,
    JSON_VALUE(row_data, '$.asset_fqn')      AS asset_fqn,
    JSON_VALUE(row_data, '$.direction')      AS direction,
    JSON_VALUE(row_data, '$.source_fqn')     AS source_fqn,
    JSON_VALUE(row_data, '$.target_fqn')     AS target_fqn,
    JSON_VALUE(row_data, '$.source_column')  AS source_column,
    JSON_VALUE(row_data, '$.target_column')  AS target_column,
    JSON_VALUE(row_data, '$.process_name')   AS process_name,
    JSON_VALUE(row_data, '$.process_kind')   AS process_kind,
    JSON_VALUE(row_data, '$.lineage_source') AS lineage_source,
    JSON_VALUE(row_data, '$.confidence')     AS confidence,
    TIMESTAMP(JSON_VALUE(row_data, '$.observed_at')) AS observed_at,
    TIMESTAMP(JSON_VALUE(row_data, '$.fetched_at'))  AS fetched_at
  FROM UNNEST(JSON_QUERY_ARRAY(@rows_json)) AS row_data
) AS source
ON  target.project_id    = source.project_id
AND target.dataset_id    = source.dataset_id
AND target.asset         = source.asset
AND target.direction     = source.direction
AND target.lineage_source = source.lineage_source
AND target.source_fqn   IS NOT DISTINCT FROM source.source_fqn
AND target.target_fqn   IS NOT DISTINCT FROM source.target_fqn
AND target.source_column IS NOT DISTINCT FROM source.source_column
AND target.target_column IS NOT DISTINCT FROM source.target_column
WHEN NOT MATCHED THEN INSERT (
  project_id, dataset_id, asset, asset_fqn,
  direction, source_fqn, target_fqn, source_column, target_column,
  process_name, process_kind, lineage_source, confidence,
  observed_at, fetched_at
) VALUES (
  source.project_id, source.dataset_id, source.asset, source.asset_fqn,
  source.direction, source.source_fqn, source.target_fqn,
  source.source_column, source.target_column,
  source.process_name, source.process_kind,
  source.lineage_source, source.confidence,
  source.observed_at, source.fetched_at
)
"""


class MergeResult:
    """Result of a lineage MERGE operation."""

    def __init__(self, inserted: int, unchanged: int) -> None:
        self.inserted = inserted
        self.unchanged = unchanged

    def __repr__(self) -> str:
        return f"MergeResult(inserted={self.inserted}, unchanged={self.unchanged})"


def merge_lineage_edges(
    client: bigquery.Client,
    edges: list[LineageEdge],
    catalog_project_id: str,
    catalog_dataset_id: str,
    table_id: str = _DEFAULT_TABLE,
) -> MergeResult:
    """MERGE lineage edges into lineage_registry using a single BQ call.

    The MERGE does not UPDATE existing rows — duplicate edges (same composite key)
    are simply not re-inserted. This keeps the table stable on re-runs.

    Args:
        client: Authenticated BigQuery client.
        edges: Edges to merge. Empty list → returns 0/0 immediately.
        catalog_project_id: GCP project that hosts catalog_registry.
        catalog_dataset_id: Dataset name (e.g. "catalog_registry").
        table_id: Target table name (default: "lineage_registry").

    Returns:
        MergeResult with inserted and unchanged counts.
    """
    if not edges:
        return MergeResult(inserted=0, unchanged=0)

    rows_json = json.dumps([e.to_bq_dict() for e in edges])

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
        "merge_lineage_edges_start",
        catalog_project=catalog_project_id,
        catalog_dataset=catalog_dataset_id,
        edge_count=len(edges),
    )

    job = client.query(sql, job_config=job_config)
    job.result()

    inserted = 0
    if job.dml_stats:
        inserted = job.dml_stats.inserted_row_count or 0
    unchanged = max(0, len(edges) - inserted)

    logger.info(
        "merge_lineage_edges_done",
        inserted=inserted,
        unchanged=unchanged,
    )
    return MergeResult(inserted=inserted, unchanged=unchanged)


def merge_lineage_report(
    client: bigquery.Client,
    report: LineageReport,
    catalog_project_id: str,
    catalog_dataset_id: str,
) -> MergeResult:
    """Convenience wrapper: merge all edges in a LineageReport."""
    return merge_lineage_edges(
        client=client,
        edges=report.edges,
        catalog_project_id=catalog_project_id,
        catalog_dataset_id=catalog_dataset_id,
    )
