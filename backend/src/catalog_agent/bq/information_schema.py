"""Queries against BigQuery INFORMATION_SCHEMA views.

Each function issues exactly one BQ query. The crawler assembles CatalogRows
by joining the results in Python — keeping queries simple and individually testable.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from google.cloud import bigquery

logger = structlog.get_logger(__name__)


@dataclass
class BQTableInfo:
    """Metadata for one table/view from INFORMATION_SCHEMA.TABLES."""

    table_name: str
    table_type: str  # "BASE TABLE" | "VIEW" | "MATERIALIZED VIEW" | "EXTERNAL" | ...
    creation_time: datetime | None
    last_modified_time: datetime | None
    row_count: int | None
    size_bytes: int | None
    clustering_fields: list[str]
    time_partitioning_type: str | None
    time_partitioning_field: str | None
    time_partitioning_expiration_ms: int | None
    range_partitioning_field: str | None
    ddl: str | None


@dataclass
class BQColumnInfo:
    """Metadata for one column from INFORMATION_SCHEMA.COLUMNS."""

    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    description: str | None


@dataclass
class BQRoutineInfo:
    """Metadata for one routine from INFORMATION_SCHEMA.ROUTINES."""

    routine_name: str
    routine_type: str  # "PROCEDURE" | "FUNCTION" | "TABLE FUNCTION"
    routine_definition: str | None


def _fq(project_id: str, dataset_id: str, view: str) -> str:
    """Return a fully-qualified INFORMATION_SCHEMA view reference."""
    return f"`{project_id}.{dataset_id}.INFORMATION_SCHEMA.{view}`"


def list_tables(client: bigquery.Client, project_id: str, dataset_id: str) -> list[BQTableInfo]:
    """Fetch table/view metadata from INFORMATION_SCHEMA.TABLES.

    Args:
        client: Authenticated BigQuery client.
        project_id: GCP project of the dataset to inspect.
        dataset_id: Dataset to inspect.

    Returns:
        One BQTableInfo per table/view/external/snapshot in the dataset.
    """
    # Only select the ANSI-standard columns that are present in all BQ editions.
    # Extended fields (row_count, size_bytes, clustering_fields, partitioning, last_modified_time)
    # are not available in all BQ project configurations — they default to None here.
    # A future enhancement can populate them via client.get_table() per-table calls.
    query = f"""
    SELECT
      table_name,
      table_type,
      creation_time,
      ddl
    FROM {_fq(project_id, dataset_id, "TABLES")}
    ORDER BY table_name
    """
    logger.info("is_query_tables", project_id=project_id, dataset_id=dataset_id)
    rows = client.query(query).result()
    return [
        BQTableInfo(
            table_name=row.table_name,
            table_type=row.table_type,
            creation_time=row.creation_time,
            last_modified_time=None,
            row_count=None,
            size_bytes=None,
            clustering_fields=[],
            time_partitioning_type=None,
            time_partitioning_field=None,
            time_partitioning_expiration_ms=None,
            range_partitioning_field=None,
            ddl=row.ddl,
        )
        for row in rows
    ]


def list_columns(client: bigquery.Client, project_id: str, dataset_id: str) -> list[BQColumnInfo]:
    """Fetch column metadata for the entire dataset in one query.

    Args:
        client: Authenticated BigQuery client.
        project_id: GCP project of the dataset.
        dataset_id: Dataset to inspect.

    Returns:
        All columns across all tables in the dataset, ordered by table then position.
    """
    fq = _fq(project_id, dataset_id, "COLUMNS")
    query_with_desc = f"""
    SELECT
      table_name,
      column_name,
      ordinal_position,
      data_type,
      description
    FROM {fq}
    ORDER BY table_name, ordinal_position
    """
    query_without_desc = f"""
    SELECT
      table_name,
      column_name,
      ordinal_position,
      data_type
    FROM {fq}
    ORDER BY table_name, ordinal_position
    """
    logger.info("is_query_columns", project_id=project_id, dataset_id=dataset_id)
    try:
        rows = list(client.query(query_with_desc).result())
        return [
            BQColumnInfo(
                table_name=row.table_name,
                column_name=row.column_name,
                ordinal_position=row.ordinal_position,
                data_type=row.data_type,
                description=row.description or None,
            )
            for row in rows
        ]
    except Exception as exc:
        if "description" not in str(exc).lower():
            raise
        logger.info("is_query_columns_no_description_fallback", reason=str(exc)[:120])
        rows = list(client.query(query_without_desc).result())
        return [
            BQColumnInfo(
                table_name=row.table_name,
                column_name=row.column_name,
                ordinal_position=row.ordinal_position,
                data_type=row.data_type,
                description=None,
            )
            for row in rows
        ]


def list_routines(client: bigquery.Client, project_id: str, dataset_id: str) -> list[BQRoutineInfo]:
    """Fetch routine (stored procedure / function) metadata.

    Args:
        client: Authenticated BigQuery client.
        project_id: GCP project of the dataset.
        dataset_id: Dataset to inspect.

    Returns:
        One BQRoutineInfo per routine in the dataset.
    """
    query = f"""
    SELECT
      routine_name,
      routine_type,
      routine_definition
    FROM {_fq(project_id, dataset_id, "ROUTINES")}
    ORDER BY routine_name
    """
    logger.info("is_query_routines", project_id=project_id, dataset_id=dataset_id)
    rows = client.query(query).result()
    return [
        BQRoutineInfo(
            routine_name=row.routine_name,
            routine_type=row.routine_type,
            routine_definition=row.routine_definition,
        )
        for row in rows
    ]


def get_table_options(
    client: bigquery.Client, project_id: str, dataset_id: str
) -> dict[str, dict[str, Any]]:
    """Fetch table-level options (description, labels) from INFORMATION_SCHEMA.TABLE_OPTIONS.

    Returns a dict keyed by table_name:
        {
            "my_table": {
                "description": "...",
                "labels": {"key": "value", ...}
            }
        }

    Args:
        client: Authenticated BigQuery client.
        project_id: GCP project of the dataset.
        dataset_id: Dataset to inspect.
    """
    query = f"""
    SELECT
      table_name,
      option_name,
      option_value
    FROM {_fq(project_id, dataset_id, "TABLE_OPTIONS")}
    WHERE option_name IN ('description', 'labels')
    ORDER BY table_name, option_name
    """
    logger.info("is_query_table_options", project_id=project_id, dataset_id=dataset_id)
    rows = client.query(query).result()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        tbl = result.setdefault(row.table_name, {})
        if row.option_name == "description":
            tbl["description"] = row.option_value or ""
        elif row.option_name == "labels":
            tbl["labels"] = _parse_labels(row.option_value)

    return result


def _parse_labels(option_value: str | None) -> dict[str, str]:
    """Parse the TABLE_OPTIONS label string into a Python dict.

    BQ stores labels as: [STRUCT("key1", "val1"), STRUCT("key2", "val2"), ...]
    """
    if not option_value:
        return {}
    pattern = re.compile(r'STRUCT\("([^"]+)",\s*"([^"]+)"\)')
    return dict(pattern.findall(option_value))
