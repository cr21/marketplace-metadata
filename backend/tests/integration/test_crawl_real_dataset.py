"""Integration tests for the catalog crawler + writer.

These tests hit a real BigQuery project and require live credentials.
Run with: BQ_INTEGRATION=1 uv run pytest -m bq

The tests use the catalog_registry dataset itself as a convenient target
(it already exists and is always accessible with the project credentials).
"""

import os

import pytest

from catalog_agent.bq.client import get_bq_client
from catalog_agent.bq.writer import merge_catalog_rows
from catalog_agent.catalog.crawler import crawl_dataset
from catalog_agent.config import get_settings

# Guard — skip unless explicitly requested
pytestmark = pytest.mark.bq
if not os.getenv("BQ_INTEGRATION"):
    pytest.skip("Set BQ_INTEGRATION=1 to run integration tests", allow_module_level=True)


@pytest.fixture(scope="module")
def settings():  # type: ignore[return]
    return get_settings()


@pytest.fixture(scope="module")
def bq_client(settings):  # type: ignore[return]
    return get_bq_client(settings)


def test_crawl_returns_rows(bq_client, settings) -> None:  # type: ignore[no-untyped-def]
    rows = crawl_dataset(bq_client, settings.gcp_project_id, settings.catalog_dataset)
    assert len(rows) >= 1, "Expected at least one asset in the catalog_registry dataset"
    for row in rows:
        assert row.asset_type in {
            "TABLE",
            "VIEW",
            "MATERIALIZED_VIEW",
            "EXTERNAL",
            "ROUTINE",
        }, f"Unexpected asset_type: {row.asset_type}"
        assert row.project_id == settings.gcp_project_id
        assert row.dataset_id == settings.catalog_dataset


def test_merge_succeeds(bq_client, settings) -> None:  # type: ignore[no-untyped-def]
    rows = crawl_dataset(bq_client, settings.gcp_project_id, settings.catalog_dataset)
    result = merge_catalog_rows(
        bq_client,
        rows,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )
    # After any prior test run, there will be existing rows; inserted may be 0.
    assert result.inserted >= 0
    assert result.updated >= 0
    assert result.unchanged >= 0
    assert result.inserted + result.updated + result.unchanged == len(rows)


def test_idempotency(bq_client, settings) -> None:  # type: ignore[no-untyped-def]
    """Two successive merges of the same crawl data must produce 0 inserts and 0 updates."""
    rows = crawl_dataset(bq_client, settings.gcp_project_id, settings.catalog_dataset)

    # First merge — may insert/update if data changed since last run
    merge_catalog_rows(
        bq_client,
        rows,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )

    # Second merge with the exact same rows — must be fully idempotent
    result2 = merge_catalog_rows(
        bq_client,
        rows,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )
    assert result2.inserted == 0, "Second merge must insert 0 rows"
    assert result2.updated == 0, "Second merge must update 0 rows"


def test_routines_have_empty_columns(bq_client, settings) -> None:  # type: ignore[no-untyped-def]
    rows = crawl_dataset(bq_client, settings.gcp_project_id, settings.catalog_dataset)
    routines = [r for r in rows if r.asset_type == "ROUTINE"]
    for routine in routines:
        assert routine.columns == [], f"Routine {routine.asset} should have empty columns"
        assert "routine_definition" in routine.table_metadata
