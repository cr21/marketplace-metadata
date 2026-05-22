"""JOBS_BY_PROJECT fallback for table-level and column-level lineage.

When the Lineage API returns no edges for an asset, these functions query
INFORMATION_SCHEMA.JOBS_BY_PROJECT to derive edges from BQ job history.

Table-level edges get confidence="MEDIUM".
Column-level edges (ENABLE_JOBS_COLUMN_INFERENCE=1) get confidence="LOW".
All values are passed as BQ query parameters — never templated into SQL strings.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from catalog_agent.lineage.models import LineageEdge

logger = structlog.get_logger(__name__)

# Only DML statement types that create meaningful lineage
_LINEAGE_STATEMENT_TYPES = [
    "CREATE_TABLE_AS_SELECT",
    "INSERT",
    "MERGE",
    "UPDATE",
]

# Table-level query: derives UPSTREAM and DOWNSTREAM edges from job history.
# Produces one row per (job, source_table, destination_table) combination.
# "source_table" is always the upstream; "destination_table" is the downstream.
# The filter on statement_type ensures we only count write-producing jobs.
_TABLE_LINEAGE_SQL = """
WITH job_lineage AS (
  SELECT
    job_id,
    creation_time,
    destination_table.project_id  AS dest_project,
    destination_table.dataset_id  AS dest_dataset,
    destination_table.table_id    AS dest_table,
    ref.project_id                AS src_project,
    ref.dataset_id                AS src_dataset,
    ref.table_id                  AS src_table
  FROM
    `{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`,
    UNNEST(referenced_tables) AS ref
  WHERE
    creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)
    AND state = 'DONE'
    AND error_result IS NULL
    AND statement_type IN UNNEST(@statement_types)
    AND destination_table IS NOT NULL
    AND destination_table.dataset_id = @dataset_id
    AND destination_table.project_id = @project_id
)
SELECT
  dest_project,
  dest_dataset,
  dest_table,
  src_project,
  src_dataset,
  src_table,
  MIN(creation_time) AS observed_at
FROM job_lineage
GROUP BY
  dest_project, dest_dataset, dest_table,
  src_project, src_dataset, src_table
"""

# Column-level inference: extends the table query with a LIKE join on column names.
# Only runs when ENABLE_JOBS_COLUMN_INFERENCE=1. confidence="LOW".
# Requires minimum column name length of 3 to reduce false positives.
_COLUMN_LINEAGE_SQL = """
WITH job_lineage AS (
  SELECT
    j.job_id,
    j.creation_time,
    j.query,
    j.destination_table.project_id  AS dest_project,
    j.destination_table.dataset_id  AS dest_dataset,
    j.destination_table.table_id    AS dest_table,
    ref.project_id                  AS src_project,
    ref.dataset_id                  AS src_dataset,
    ref.table_id                    AS src_table
  FROM
    `{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT` j,
    UNNEST(j.referenced_tables) AS ref
  WHERE
    j.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)
    AND j.state = 'DONE'
    AND j.error_result IS NULL
    AND j.statement_type IN UNNEST(@statement_types)
    AND j.destination_table IS NOT NULL
    AND j.destination_table.dataset_id = @dataset_id
    AND j.destination_table.project_id = @project_id
),
all_columns AS (
  SELECT
    c.table_catalog AS col_project,
    c.table_schema  AS col_dataset,
    c.table_name    AS col_table,
    c.column_name
  FROM `{info_schema_region}.INFORMATION_SCHEMA.COLUMNS` c
  WHERE
    c.table_schema = @dataset_id
    AND c.table_catalog = @project_id
    AND LENGTH(c.column_name) >= 3
)
SELECT
  jl.dest_project,
  jl.dest_dataset,
  jl.dest_table,
  jl.src_project,
  jl.src_dataset,
  jl.src_table,
  ac.column_name                AS inferred_column,
  MIN(jl.creation_time)         AS observed_at
FROM job_lineage jl
JOIN all_columns ac
  ON  jl.src_project = ac.col_project
  AND jl.src_dataset  = ac.col_dataset
  AND jl.src_table    = ac.col_table
WHERE LOWER(jl.query) LIKE CONCAT('%', LOWER(ac.column_name), '%')
GROUP BY
  jl.dest_project, jl.dest_dataset, jl.dest_table,
  jl.src_project, jl.src_dataset, jl.src_table,
  ac.column_name
"""


def _jobs_region(location: str) -> str:
    """Return the INFORMATION_SCHEMA region prefix for a given location.

    e.g. "us" -> "region-us", "us-central1" -> "region-us-central1"
    """
    return f"region-{location}"


def fetch_table_lineage_from_jobs(
    bq_client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    asset: str,
    location: str = "us",
    lookback_days: int = 90,
) -> list[LineageEdge]:
    """Derive table-level lineage edges from JOBS_BY_PROJECT.

    Args:
        bq_client: Authenticated BigQuery client.
        project_id: GCP project whose JOBS_BY_PROJECT to query.
        dataset_id: Dataset containing ``asset``.
        asset: Asset name. Edges are filtered to those where ``asset`` is
            the destination table (UPSTREAM direction) or source (DOWNSTREAM).
        location: Dataset region (e.g. ``"us"``). Used to build the
            region-scoped INFORMATION_SCHEMA path.
        lookback_days: How many days of job history to scan (max 180).

    Returns:
        List of LineageEdge with confidence="MEDIUM". Empty on error.
    """
    region = _jobs_region(location)
    sql = _TABLE_LINEAGE_SQL.format(region=region)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("lookback_days", "INT64", lookback_days),
            bigquery.ArrayQueryParameter("statement_types", "STRING", _LINEAGE_STATEMENT_TYPES),
        ]
    )

    fetched_at = datetime.now(UTC)
    try:
        rows = list(bq_client.query(sql, job_config=job_config).result())
    except gcp_exceptions.Forbidden as exc:
        logger.warning(
            "jobs_fallback_permission_denied",
            project_id=project_id,
            error=str(exc),
        )
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("jobs_fallback_error", project_id=project_id, error=str(exc))
        return []

    edges: list[LineageEdge] = []
    asset_fqn = f"{project_id}.{dataset_id}.{asset}"

    for row in rows:
        dest_fqn = f"{row.dest_project}.{row.dest_dataset}.{row.dest_table}"
        src_fqn = f"{row.src_project}.{row.src_dataset}.{row.src_table}"
        observed_at: datetime = row.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)

        # Only emit edges involving our target asset
        is_dest = row.dest_table == asset and row.dest_dataset == dataset_id
        is_src = row.src_table == asset and row.src_dataset == dataset_id

        if is_dest:
            edges.append(
                LineageEdge(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    asset=asset,
                    asset_fqn=asset_fqn,
                    direction="UPSTREAM",
                    source_fqn=src_fqn,
                    target_fqn=dest_fqn,
                    source_column=None,
                    target_column=None,
                    process_name=None,
                    process_kind="JOBS_HISTORY",
                    lineage_source="JOBS_FALLBACK",
                    confidence="MEDIUM",
                    observed_at=observed_at,
                    fetched_at=fetched_at,
                )
            )
        if is_src:
            edges.append(
                LineageEdge(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    asset=asset,
                    asset_fqn=asset_fqn,
                    direction="DOWNSTREAM",
                    source_fqn=src_fqn,
                    target_fqn=dest_fqn,
                    source_column=None,
                    target_column=None,
                    process_name=None,
                    process_kind="JOBS_HISTORY",
                    lineage_source="JOBS_FALLBACK",
                    confidence="MEDIUM",
                    observed_at=observed_at,
                    fetched_at=fetched_at,
                )
            )

    logger.debug(
        "jobs_fallback_table_lineage",
        project_id=project_id,
        dataset_id=dataset_id,
        asset=asset,
        edge_count=len(edges),
    )
    return edges


def fetch_column_lineage_from_jobs(
    bq_client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    asset: str,
    location: str = "us",
    lookback_days: int = 90,
) -> list[LineageEdge]:
    """Infer column-level lineage edges from JOBS_BY_PROJECT query text (LOW confidence).

    Uses substring matching of column names against the job's query text.
    Only runs when ENABLE_JOBS_COLUMN_INFERENCE is enabled. Column names
    shorter than 3 characters are excluded at the SQL level.

    Returns edges with confidence="LOW". Returns [] on error.
    """
    region = _jobs_region(location)
    # INFORMATION_SCHEMA.COLUMNS uses the dataset's region directly (not region-prefixed)
    info_schema_region = f"{project_id}.{dataset_id}"
    sql = _COLUMN_LINEAGE_SQL.format(region=region, info_schema_region=info_schema_region)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("lookback_days", "INT64", lookback_days),
            bigquery.ArrayQueryParameter("statement_types", "STRING", _LINEAGE_STATEMENT_TYPES),
        ]
    )

    fetched_at = datetime.now(UTC)
    try:
        rows = list(bq_client.query(sql, job_config=job_config).result())
    except gcp_exceptions.Forbidden as exc:
        logger.warning(
            "jobs_column_inference_permission_denied",
            project_id=project_id,
            error=str(exc),
        )
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("jobs_column_inference_error", project_id=project_id, error=str(exc))
        return []

    edges: list[LineageEdge] = []
    asset_fqn = f"{project_id}.{dataset_id}.{asset}"

    for row in rows:
        is_dest = row.dest_table == asset and row.dest_dataset == dataset_id
        if not is_dest:
            continue

        src_fqn = f"{row.src_project}.{row.src_dataset}.{row.src_table}"
        dest_fqn = f"{row.dest_project}.{row.dest_dataset}.{row.dest_table}"
        observed_at: datetime = row.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)

        edges.append(
            LineageEdge(
                project_id=project_id,
                dataset_id=dataset_id,
                asset=asset,
                asset_fqn=asset_fqn,
                direction="UPSTREAM",
                source_fqn=src_fqn,
                target_fqn=dest_fqn,
                source_column=row.inferred_column,
                target_column=None,
                process_name=None,
                process_kind="JOBS_HISTORY",
                lineage_source="JOBS_FALLBACK",
                confidence="LOW",
                observed_at=observed_at,
                fetched_at=fetched_at,
            )
        )

    logger.debug(
        "jobs_fallback_column_lineage",
        project_id=project_id,
        dataset_id=dataset_id,
        asset=asset,
        edge_count=len(edges),
    )
    return edges
