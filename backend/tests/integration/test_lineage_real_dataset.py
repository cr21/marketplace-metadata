"""Integration tests for the lineage fetcher against a real BigQuery project.

These tests require real GCP credentials and a test dataset with known lineage.
They are gated by @pytest.mark.bq and only run when BQ_INTEGRATION=1.

Run with:
    BQ_INTEGRATION=1 uv run pytest -m bq tests/integration/test_lineage_real_dataset.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest

from catalog_agent.bq.client import get_bq_client
from catalog_agent.config import get_settings
from catalog_agent.lineage.client import LineageApiClient
from catalog_agent.lineage.fetcher import fetch_lineage_for_dataset
from catalog_agent.lineage.jobs_fallback import fetch_table_lineage_from_jobs
from catalog_agent.lineage.models import LineageReport
from catalog_agent.lineage.writer import merge_lineage_report

pytestmark = pytest.mark.bq

_TEST_DATASET = os.getenv("TEST_LINEAGE_DATASET", "catalog_registry")


@pytest.fixture(scope="module")
def settings():  # type: ignore[no-untyped-def]
    return get_settings()


@pytest.fixture(scope="module")
def bq_client(settings):  # type: ignore[no-untyped-def]
    return get_bq_client(settings)


@pytest.fixture(scope="module")
def lineage_client(settings):  # type: ignore[no-untyped-def]
    return LineageApiClient(
        project_id=settings.gcp_project_id,
        location=settings.lineage_location,
    )


def _get_catalog_assets(bq_client, settings, dataset_id: str) -> list[str]:  # type: ignore[no-untyped-def]
    """Fetch asset names from data_catalog_registry for a given dataset."""
    from google.cloud import bigquery

    sql = f"""
        SELECT DISTINCT asset
        FROM `{settings.gcp_project_id}.{settings.catalog_dataset}.data_catalog_registry`
        WHERE project_id = @project_id AND dataset_id = @dataset_id
        LIMIT 10
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", settings.gcp_project_id),
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
        ]
    )
    rows = list(bq_client.query(sql, job_config=job_config).result())
    return [r.asset for r in rows]


@pytest.mark.skipif(
    os.getenv("BQ_INTEGRATION") != "1",
    reason="BQ_INTEGRATION=1 required",
)
def test_fetch_lineage_returns_report(bq_client, lineage_client, settings):  # type: ignore[no-untyped-def]
    """fetch_lineage_for_dataset returns a LineageReport (may be empty if no lineage)."""
    assets = _get_catalog_assets(bq_client, settings, _TEST_DATASET)
    if not assets:
        pytest.skip(f"No catalog rows for dataset {_TEST_DATASET} — run demo-m01 first.")

    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id=settings.gcp_project_id,
            dataset_id=_TEST_DATASET,
            assets=assets[:5],  # limit to 5 for speed
            settings=settings,
        )
    )

    assert isinstance(report, LineageReport)
    assert report.project_id == settings.gcp_project_id
    assert report.dataset_id == _TEST_DATASET
    # Edges may be empty for a dataset without known lineage — that's OK
    for edge in report.edges:
        assert edge.confidence in ("HIGH", "MEDIUM", "LOW")
        assert edge.lineage_source in ("LINEAGE_API", "JOBS_FALLBACK")


@pytest.mark.skipif(
    os.getenv("BQ_INTEGRATION") != "1",
    reason="BQ_INTEGRATION=1 required",
)
def test_merge_lineage_idempotent(bq_client, lineage_client, settings):  # type: ignore[no-untyped-def]
    """Writing the same report twice produces inserted=0 on the second run."""
    assets = _get_catalog_assets(bq_client, settings, _TEST_DATASET)
    if not assets:
        pytest.skip(f"No catalog rows for dataset {_TEST_DATASET} — run demo-m01 first.")

    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id=settings.gcp_project_id,
            dataset_id=_TEST_DATASET,
            assets=assets[:3],
            settings=settings,
        )
    )

    if not report.edges:
        pytest.skip("No lineage edges found — idempotency test requires at least one edge.")

    # First write
    merge_lineage_report(
        client=bq_client,
        report=report,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )
    # Second write — same data → zero new inserts
    result2 = merge_lineage_report(
        client=bq_client,
        report=report,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )

    assert result2.inserted == 0, "Second write must not insert duplicate rows"


@pytest.mark.skipif(
    os.getenv("BQ_INTEGRATION") != "1",
    reason="BQ_INTEGRATION=1 required",
)
def test_jobs_fallback_runs_without_error(bq_client, settings):  # type: ignore[no-untyped-def]
    """JOBS fallback completes without error (edges may be empty)."""
    assets = _get_catalog_assets(bq_client, settings, _TEST_DATASET)
    if not assets:
        pytest.skip("No catalog rows found.")

    edges = fetch_table_lineage_from_jobs(
        bq_client=bq_client,
        project_id=settings.gcp_project_id,
        dataset_id=_TEST_DATASET,
        asset=assets[0],
        location=settings.lineage_location,
        lookback_days=90,
    )

    for edge in edges:
        assert edge.confidence == "MEDIUM"
        assert edge.lineage_source == "JOBS_FALLBACK"
        assert edge.source_column is None
        assert edge.target_column is None


@pytest.mark.skipif(
    os.getenv("BQ_INTEGRATION") != "1",
    reason="BQ_INTEGRATION=1 required",
)
def test_empty_dataset_writes_zero_rows(bq_client, lineage_client, settings):  # type: ignore[no-untyped-def]
    """An asset with no lineage writes zero rows without error."""
    from catalog_agent.lineage.writer import merge_lineage_edges

    result = merge_lineage_edges(
        client=bq_client,
        edges=[],
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )
    assert result.inserted == 0
    assert result.unchanged == 0
