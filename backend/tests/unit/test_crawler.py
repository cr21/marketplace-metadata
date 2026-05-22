"""Unit tests for the catalog crawler.

All BigQuery calls are mocked — no real credentials needed.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from catalog_agent.bq.information_schema import (
    BQColumnInfo,
    BQRoutineInfo,
    BQTableInfo,
)
from catalog_agent.catalog.crawler import crawl_dataset


def _make_table(
    name: str = "orders",
    table_type: str = "BASE TABLE",
    row_count: int | None = 100,
    size_bytes: int | None = 1024,
    clustering_fields: list[str] | None = None,
    time_partitioning_type: str | None = None,
    time_partitioning_field: str | None = None,
) -> BQTableInfo:
    return BQTableInfo(
        table_name=name,
        table_type=table_type,
        creation_time=datetime(2024, 1, 1, tzinfo=UTC),
        last_modified_time=datetime(2024, 6, 1, tzinfo=UTC),
        row_count=row_count,
        size_bytes=size_bytes,
        clustering_fields=clustering_fields or [],
        time_partitioning_type=time_partitioning_type,
        time_partitioning_field=time_partitioning_field,
        time_partitioning_expiration_ms=None,
        range_partitioning_field=None,
        ddl=None,
    )


def _make_column(
    table: str,
    name: str,
    data_type: str = "STRING",
    ordinal: int = 1,
    description: str | None = None,
) -> BQColumnInfo:
    return BQColumnInfo(
        table_name=table,
        column_name=name,
        ordinal_position=ordinal,
        data_type=data_type,
        description=description,
    )


@pytest.fixture
def mock_bq_client() -> MagicMock:
    return MagicMock()


def _patch_is(tables: list, columns: list, routines: list, options: dict):  # type: ignore[type-arg]
    """Return a context manager that patches all four IS query functions."""
    return (
        patch("catalog_agent.catalog.crawler.list_tables", return_value=tables),
        patch("catalog_agent.catalog.crawler.list_columns", return_value=columns),
        patch("catalog_agent.catalog.crawler.list_routines", return_value=routines),
        patch("catalog_agent.catalog.crawler.get_table_options", return_value=options),
    )


def test_crawl_basic_table(mock_bq_client: MagicMock) -> None:
    tables = [_make_table("orders")]
    cols = [
        _make_column("orders", "id", "INT64", 1),
        _make_column("orders", "email", "STRING", 2),
    ]

    p1, p2, p3, p4 = _patch_is(tables, cols, [], {})
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    assert len(rows) == 1
    row = rows[0]
    assert row.asset == "orders"
    assert row.asset_type == "TABLE"
    assert row.project_id == "proj"
    assert row.dataset_id == "ds"
    assert len(row.columns) == 2


def test_crawl_asset_type_mapping(mock_bq_client: MagicMock) -> None:
    tables = [
        _make_table("t1", "BASE TABLE"),
        _make_table("t2", "VIEW"),
        _make_table("t3", "MATERIALIZED VIEW"),
        _make_table("t4", "EXTERNAL"),
    ]

    p1, p2, p3, p4 = _patch_is(tables, [], [], {})
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    type_map = {r.asset: r.asset_type for r in rows}
    assert type_map["t1"] == "TABLE"
    assert type_map["t2"] == "VIEW"
    assert type_map["t3"] == "MATERIALIZED_VIEW"
    assert type_map["t4"] == "EXTERNAL"


def test_crawl_pii_tagging(mock_bq_client: MagicMock) -> None:
    cols = [
        _make_column("users", "id", "INT64", 1),
        _make_column("users", "email", "STRING", 2),
        _make_column("users", "phone_number", "STRING", 3),
        _make_column("users", "created_at", "TIMESTAMP", 4),
    ]

    p1, p2, p3, p4 = _patch_is([_make_table("users")], cols, [], {})
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    col_map = {c.name: c for c in rows[0].columns}
    assert col_map["id"].is_pii is False
    assert col_map["email"].is_pii is True
    assert col_map["phone_number"].is_pii is True
    assert col_map["created_at"].is_pii is False


def test_crawl_routine_has_empty_columns(mock_bq_client: MagicMock) -> None:
    routine = BQRoutineInfo(
        routine_name="sp_load_orders",
        routine_type="PROCEDURE",
        routine_definition="BEGIN SELECT 1; END",
    )

    p1, p2, p3, p4 = _patch_is([], [], [routine], {})
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    assert len(rows) == 1
    row = rows[0]
    assert row.asset == "sp_load_orders"
    assert row.asset_type == "ROUTINE"
    assert row.columns == []
    assert row.table_metadata["routine_definition"] == "BEGIN SELECT 1; END"


def test_crawl_table_metadata_structure(mock_bq_client: MagicMock) -> None:
    tables = [
        _make_table(
            "partitioned",
            clustering_fields=["region"],
            time_partitioning_type="DAY",
            time_partitioning_field="created_at",
        )
    ]
    options = {"partitioned": {"description": "My table", "labels": {"env": "prod"}}}

    p1, p2, p3, p4 = _patch_is(tables, [], [], options)
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    meta = rows[0].table_metadata
    assert meta["description"] == "My table"
    assert meta["labels"] == {"env": "prod"}
    assert meta["clustering_fields"] == ["region"]
    assert meta["partitioning"]["type"] == "DAY"
    assert meta["partitioning"]["field"] == "created_at"


def test_crawl_table_metadata_json_is_deterministic(mock_bq_client: MagicMock) -> None:
    """table_metadata JSON must be identical across two equivalent crawl runs (idempotency)."""
    tables = [_make_table("t")]
    cols = [_make_column("t", "id", "INT64", 1)]
    opts: dict = {}

    p1, p2, p3, p4 = _patch_is(tables, cols, [], opts)
    with p1, p2, p3, p4:
        rows1 = crawl_dataset(mock_bq_client, "proj", "ds")

    p1, p2, p3, p4 = _patch_is(tables, cols, [], opts)
    with p1, p2, p3, p4:
        rows2 = crawl_dataset(mock_bq_client, "proj", "ds")

    assert rows1[0].to_bq_dict()["table_metadata"] == rows2[0].to_bq_dict()["table_metadata"]


def test_crawl_column_description_from_information_schema(mock_bq_client: MagicMock) -> None:
    cols = [_make_column("t", "user_id", "INT64", 1, description="Unique user identifier")]
    p1, p2, p3, p4 = _patch_is([_make_table("t")], cols, [], {})
    with p1, p2, p3, p4:
        rows = crawl_dataset(mock_bq_client, "proj", "ds")

    assert rows[0].columns[0].description == "Unique user identifier"


def test_crawl_no_openai_when_client_is_none(mock_bq_client: MagicMock) -> None:
    """When openai_client is None, enricher is never called."""
    p1, p2, p3, p4 = _patch_is([_make_table("t")], [], [], {})
    with p1, p2, p3, p4, patch("catalog_agent.catalog.crawler.enrich_catalog_row") as mock_enrich:
        # enrich_catalog_row is imported lazily inside the if-block, so we patch the module
        crawl_dataset(mock_bq_client, "proj", "ds", openai_client=None)
        mock_enrich.assert_not_called()
