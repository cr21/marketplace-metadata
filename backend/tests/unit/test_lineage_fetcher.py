"""Unit tests for the lineage fetcher.

All Lineage API and BQ calls are mocked — no real GCP credentials needed.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

from catalog_agent.config import Settings
from catalog_agent.lineage.client import LineageApiClient, make_asset_fqn
from catalog_agent.lineage.fetcher import (
    fetch_asset_lineage,
    fetch_column_lineage,
    fetch_lineage_for_dataset,
)
from catalog_agent.lineage.models import LineageEdge, LineageReport

# ─── helpers ──────────────────────────────────────────────────────────────────


def _settings(**overrides: object) -> Settings:
    base = {
        "gcp_project_id": "test-project",
        "catalog_dataset": "catalog_registry",
        "lineage_location": "us",
        "lineage_fetch_concurrency": 2,
        "jobs_fallback_lookback_days": 90,
        "enable_jobs_column_inference": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _mock_link(source_fqn: str, target_fqn: str) -> MagicMock:
    link = MagicMock()
    link.source.fully_qualified_name = source_fqn
    link.target.fully_qualified_name = target_fqn
    link.name = f"projects/p/locations/us/links/{source_fqn}-{target_fqn}"
    link.start_time = None
    return link


def _mock_lineage_client(
    upstream_links: list[MagicMock] | None = None,
    downstream_links: list[MagicMock] | None = None,
    process_links: list[MagicMock] | None = None,
) -> LineageApiClient:
    client = MagicMock(spec=LineageApiClient)

    def _search_links(asset_fqn: str, direction: str) -> list[MagicMock]:
        if direction == "UPSTREAM":
            return upstream_links or []
        return downstream_links or []

    client.search_links.side_effect = _search_links
    client.batch_search_link_processes.return_value = process_links or []
    return client


# ─── make_asset_fqn ───────────────────────────────────────────────────────────


def test_make_asset_fqn() -> None:
    fqn = make_asset_fqn("my-project", "my_dataset", "my_table")
    assert fqn == "bigquery:my-project.my_dataset.my_table"


# ─── fetch_asset_lineage ──────────────────────────────────────────────────────


def test_fetch_asset_lineage_upstream_and_downstream() -> None:
    upstream = _mock_link("bigquery:src.ds.src_table", "bigquery:proj.ds.asset")
    downstream = _mock_link("bigquery:proj.ds.asset", "bigquery:dest.ds.dest_table")
    client = _mock_lineage_client(upstream_links=[upstream], downstream_links=[downstream])

    edges = fetch_asset_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset")

    assert len(edges) == 2
    assert any(e.direction == "UPSTREAM" for e in edges)
    assert any(e.direction == "DOWNSTREAM" for e in edges)
    for e in edges:
        assert e.lineage_source == "LINEAGE_API"
        assert e.confidence == "HIGH"
        assert e.source_column is None
        assert e.target_column is None


def test_fetch_asset_lineage_empty() -> None:
    client = _mock_lineage_client()
    edges = fetch_asset_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset")
    assert edges == []


def test_fetch_asset_lineage_field_mapping() -> None:
    link = _mock_link("bigquery:src.src_ds.tbl", "bigquery:proj.ds.asset")
    client = _mock_lineage_client(upstream_links=[link])

    edges = fetch_asset_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset")

    assert len(edges) == 1
    e = edges[0]
    assert e.project_id == "proj"
    assert e.dataset_id == "ds"
    assert e.asset == "asset"
    assert e.asset_fqn == "bigquery:proj.ds.asset"
    assert e.source_fqn == "bigquery:src.src_ds.tbl"
    assert e.target_fqn == "bigquery:proj.ds.asset"


# ─── fetch_column_lineage ─────────────────────────────────────────────────────


def test_fetch_column_lineage_no_links_returns_empty() -> None:
    client = _mock_lineage_client()
    edges = fetch_column_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset", [])
    assert edges == []
    client.batch_search_link_processes.assert_not_called()


def test_fetch_column_lineage_no_facets_returns_table_level() -> None:
    link = _mock_link("bigquery:src.ds.tbl", "bigquery:proj.ds.asset")

    # ProcessLinks with no column facets.
    # link_info.link is a resource-name string (not a Link object).
    process_links = MagicMock()
    process_links.process = "projects/proj/locations/us/processes/abc"
    link_info = MagicMock()
    link_info.link = link.name  # string resource name
    link_info.start_time = None
    link_info.column_lineage_facets = []  # no column facets
    process_links.links = [link_info]

    client = _mock_lineage_client(process_links=[process_links])

    edges = fetch_column_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset", [link])

    assert len(edges) >= 1
    for e in edges:
        assert e.confidence == "HIGH"
        assert e.lineage_source == "LINEAGE_API"
        assert e.source_column is None
        assert e.target_column is None


def test_fetch_column_lineage_with_facets() -> None:
    link = _mock_link("bigquery:src.ds.tbl", "bigquery:proj.ds.asset")

    # Build mock column facet
    facet = MagicMock()
    field_transform = MagicMock()
    output_field = MagicMock()
    output_field.field = "email"
    input_field = MagicMock()
    input_field.field = "raw_email"
    field_transform.output_field = output_field
    field_transform.input_fields = [input_field]
    facet.field_transform_facets = [field_transform]

    process_links = MagicMock()
    process_links.process = "projects/proj/locations/us/processes/abc"
    link_info = MagicMock()
    link_info.link = link.name  # string resource name
    link_info.start_time = None
    link_info.column_lineage_facets = [facet]
    process_links.links = [link_info]

    client = _mock_lineage_client(process_links=[process_links])

    edges = fetch_column_lineage(client, "proj", "ds", "asset", "bigquery:proj.ds.asset", [link])

    col_edges = [e for e in edges if e.source_column is not None]
    assert len(col_edges) >= 1
    assert col_edges[0].source_column == "raw_email"
    assert col_edges[0].target_column == "email"
    assert col_edges[0].confidence == "HIGH"
    assert col_edges[0].lineage_source == "LINEAGE_API"


# ─── fetch_lineage_for_dataset ────────────────────────────────────────────────


def test_fetch_lineage_for_dataset_api_has_edges() -> None:
    """When Lineage API returns edges, JOBS fallback is not called."""
    upstream = _mock_link("bigquery:src.ds.tbl", "bigquery:proj.ds.asset")
    lineage_client = _mock_lineage_client(upstream_links=[upstream])
    bq_client = MagicMock()
    settings = _settings()

    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id="proj",
            dataset_id="ds",
            assets=["asset"],
            settings=settings,
        )
    )

    assert isinstance(report, LineageReport)
    assert len(report.edges) >= 1
    assert all(e.lineage_source == "LINEAGE_API" for e in report.edges)
    # BQ client should NOT have been called (no fallback needed)
    bq_client.query.assert_not_called()


def test_fetch_lineage_for_dataset_falls_back_when_api_empty() -> None:
    """When Lineage API returns nothing, the JOBS fallback is triggered."""
    lineage_client = _mock_lineage_client()  # no links

    # Mock JOBS fallback returning one edge
    mock_row = MagicMock()
    mock_row.dest_project = "proj"
    mock_row.dest_dataset = "ds"
    mock_row.dest_table = "asset"
    mock_row.src_project = "proj"
    mock_row.src_dataset = "ds"
    mock_row.src_table = "upstream_table"
    mock_row.observed_at = datetime(2024, 1, 1, tzinfo=UTC)

    mock_job = MagicMock()
    mock_job.result.return_value = [mock_row]
    bq_client = MagicMock()
    bq_client.query.return_value = mock_job
    settings = _settings()

    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id="proj",
            dataset_id="ds",
            assets=["asset"],
            settings=settings,
        )
    )

    fallback_edges = [e for e in report.edges if e.lineage_source == "JOBS_FALLBACK"]
    assert len(fallback_edges) >= 1
    assert fallback_edges[0].confidence == "MEDIUM"


def test_fetch_lineage_for_dataset_no_edges_at_all() -> None:
    """Asset with no lineage from any source → empty edges, no error."""
    lineage_client = _mock_lineage_client()
    mock_job = MagicMock()
    mock_job.result.return_value = []
    bq_client = MagicMock()
    bq_client.query.return_value = mock_job
    settings = _settings()

    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id="proj",
            dataset_id="ds",
            assets=["orphan_asset"],
            settings=settings,
        )
    )

    assert report.edges == []


def test_fetch_lineage_for_dataset_concurrency_respected() -> None:
    """Semaphore limits concurrent calls to lineage_fetch_concurrency."""
    import threading

    concurrent: list[int] = [0]
    peak: list[int] = [0]
    lock = threading.Lock()

    def slow_search(asset_fqn: str, direction: str) -> list[object]:
        with lock:
            concurrent[0] += 1
            peak[0] = max(peak[0], concurrent[0])
        import time

        time.sleep(0.05)
        with lock:
            concurrent[0] -= 1
        return []

    lineage_client = MagicMock(spec=LineageApiClient)
    lineage_client.search_links.side_effect = slow_search
    lineage_client.batch_search_link_processes.return_value = []

    mock_job = MagicMock()
    mock_job.result.return_value = []
    bq_client = MagicMock()
    bq_client.query.return_value = mock_job

    settings = _settings(lineage_fetch_concurrency=2)

    asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id="proj",
            dataset_id="ds",
            assets=["a", "b", "c", "d", "e"],
            settings=settings,
        )
    )

    # Each asset calls search_links twice (UPSTREAM + DOWNSTREAM)
    # Peak concurrent *asset* tasks should be ≤ concurrency setting
    assert peak[0] <= settings.lineage_fetch_concurrency * 2 + 1  # slack for thread timing


def test_fetch_lineage_for_dataset_exception_in_one_asset_does_not_crash() -> None:
    """An exception for one asset is logged; other assets still succeed."""
    call_count: list[int] = [0]

    def sometimes_raises(asset_fqn: str, direction: str) -> list[object]:
        call_count[0] += 1
        if "bad_asset" in asset_fqn:
            raise RuntimeError("Simulated API error")
        return []

    lineage_client = MagicMock(spec=LineageApiClient)
    lineage_client.search_links.side_effect = sometimes_raises
    lineage_client.batch_search_link_processes.return_value = []

    mock_job = MagicMock()
    mock_job.result.return_value = []
    bq_client = MagicMock()
    bq_client.query.return_value = mock_job
    settings = _settings()

    # Should not raise
    report = asyncio.run(
        fetch_lineage_for_dataset(
            lineage_client=lineage_client,
            bq_client=bq_client,
            project_id="proj",
            dataset_id="ds",
            assets=["good_asset", "bad_asset"],
            settings=settings,
        )
    )
    assert isinstance(report, LineageReport)


def test_lineage_report_summary_counts() -> None:
    now = datetime.now(UTC)
    base = dict(
        project_id="p",
        dataset_id="d",
        asset="a",
        asset_fqn="p.d.a",
        direction="UPSTREAM",
        lineage_source="LINEAGE_API",
        observed_at=now,
        fetched_at=now,
    )
    edges = [
        LineageEdge(**base, confidence="HIGH"),
        LineageEdge(**base, confidence="HIGH"),
        LineageEdge(**{**base, "lineage_source": "JOBS_FALLBACK"}, confidence="MEDIUM"),
        LineageEdge(**{**base, "lineage_source": "JOBS_FALLBACK"}, confidence="LOW"),
    ]
    report = LineageReport(project_id="p", dataset_id="d", edges=edges)
    assert report.high_count == 2
    assert report.medium_count == 1
    assert report.low_count == 1
    assert "HIGH: 2" in report.summary()
    assert "MEDIUM: 1" in report.summary()
    assert "LOW: 1" in report.summary()
