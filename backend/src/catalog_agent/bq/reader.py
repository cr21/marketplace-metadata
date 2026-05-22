"""Read existing catalog registry rows for incremental update comparisons."""

import structlog
from google.cloud import bigquery

logger = structlog.get_logger(__name__)


def registry_table_exists(
    client: bigquery.Client,
    registry_project: str,
    registry_dataset: str,
    table_id: str = "data_catalog_registry",
) -> bool:
    """Return True if the registry table exists in BigQuery."""
    try:
        client.get_table(f"{registry_project}.{registry_dataset}.{table_id}")
        return True
    except Exception:
        return False


def read_registry_snapshot(
    client: bigquery.Client,
    registry_project: str,
    registry_dataset: str,
    table_id: str = "data_catalog_registry",
) -> dict[tuple[str, str, str], dict] | None:
    """Read all existing registry rows into a dict for diff comparison.

    Returns a dict keyed by (project_id, dataset_id, asset) where values contain
    'table_metadata' (stored JSON string) and 'columns_json' (BQ TO_JSON_STRING).
    Returns None if the table cannot be read.
    """
    sql = f"""
    SELECT
        project_id,
        dataset_id,
        asset,
        table_metadata,
        TO_JSON_STRING(columns) AS columns_json
    FROM `{registry_project}.{registry_dataset}.{table_id}`
    """
    try:
        rows = list(client.query(sql).result())
        snapshot = {
            (row.project_id, row.dataset_id, row.asset): {
                "table_metadata": row.table_metadata or "",
                "columns_json": row.columns_json or "[]",
            }
            for row in rows
        }
        logger.info("registry_snapshot_read", row_count=len(snapshot))
        return snapshot
    except Exception as exc:
        logger.info("registry_snapshot_read_failed", error=str(exc))
        return None
