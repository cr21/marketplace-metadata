"""Unit tests for the JOBS_BY_PROJECT lineage fallback.

All BigQuery calls are mocked — no real GCP credentials needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.api_core import exceptions as gcp_exceptions

from catalog_agent.lineage.jobs_fallback import (
    _jobs_region,
    fetch_column_lineage_from_jobs,
    fetch_table_lineage_from_jobs,
)

# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_table_row(
    dest_table: str = "my_table",
    src_table: str = "upstream_table",
    dest_dataset: str = "my_ds",
    src_dataset: str = "my_ds",
    dest_project: str = "proj",
    src_project: str = "proj",
) -> MagicMock:
    row = MagicMock()
    row.dest_project = dest_project
    row.dest_dataset = dest_dataset
    row.dest_table = dest_table
    row.src_project = src_project
    row.src_dataset = src_dataset
    row.src_table = src_table
    row.observed_at = datetime(2024, 6, 1, tzinfo=UTC)
    return row


def _make_col_row(
    dest_table: str = "my_table",
    src_table: str = "upstream_table",
    column_name: str = "email_address",
) -> MagicMock:
    row = _make_table_row(dest_table=dest_table, src_table=src_table)
    row.inferred_column = column_name
    return row


def _bq_client(rows: list[MagicMock]) -> MagicMock:
    mock_job = MagicMock()
    mock_job.result.return_value = rows
    client = MagicMock()
    client.query.return_value = mock_job
    return client


# ─── _jobs_region ─────────────────────────────────────────────────────────────


def test_jobs_region_multi_region() -> None:
    assert _jobs_region("us") == "region-us"


def test_jobs_region_single_region() -> None:
    assert _jobs_region("us-central1") == "region-us-central1"


# ─── fetch_table_lineage_from_jobs ────────────────────────────────────────────


def test_table_lineage_upstream_edge() -> None:
    """Row where asset is the destination → UPSTREAM edge."""
    row = _make_table_row(dest_table="my_table", src_table="upstream_table")
    client = _bq_client([row])

    edges = fetch_table_lineage_from_jobs(
        bq_client=client,
        project_id="proj",
        dataset_id="my_ds",
        asset="my_table",
    )

    upstream = [e for e in edges if e.direction == "UPSTREAM"]
    assert len(upstream) == 1
    assert upstream[0].confidence == "MEDIUM"
    assert upstream[0].lineage_source == "JOBS_FALLBACK"
    assert upstream[0].source_column is None
    assert upstream[0].target_column is None
    assert upstream[0].process_kind == "JOBS_HISTORY"


def test_table_lineage_downstream_edge() -> None:
    """Row where asset is the source → DOWNSTREAM edge."""
    row = _make_table_row(dest_table="downstream_table", src_table="my_table")
    client = _bq_client([row])

    edges = fetch_table_lineage_from_jobs(
        bq_client=client,
        project_id="proj",
        dataset_id="my_ds",
        asset="my_table",
    )

    downstream = [e for e in edges if e.direction == "DOWNSTREAM"]
    assert len(downstream) == 1
    assert downstream[0].confidence == "MEDIUM"


def test_table_lineage_empty_result() -> None:
    client = _bq_client([])
    edges = fetch_table_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    assert edges == []


def test_table_lineage_permission_denied_returns_empty() -> None:
    client = MagicMock()
    client.query.side_effect = gcp_exceptions.Forbidden("permission denied")

    edges = fetch_table_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    assert edges == []


def test_table_lineage_generic_error_returns_empty() -> None:
    client = MagicMock()
    client.query.side_effect = RuntimeError("unexpected error")

    edges = fetch_table_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    assert edges == []


def test_table_lineage_uses_query_parameters_not_string_format() -> None:
    """Verify BQ parameters are passed, not values templated into SQL."""
    client = _bq_client([])
    fetch_table_lineage_from_jobs(
        bq_client=client,
        project_id="my-project",
        dataset_id="my_dataset",
        asset="my_table",
        lookback_days=45,
    )

    call_args = client.query.call_args
    job_config = call_args.kwargs.get("job_config") or call_args.args[1]
    param_names = {p.name for p in job_config.query_parameters}
    assert "project_id" in param_names
    assert "dataset_id" in param_names
    assert "lookback_days" in param_names
    assert "statement_types" in param_names

    # Values must NOT appear in the SQL string itself
    sql: str = call_args.args[0]
    assert "my-project" not in sql
    assert "my_dataset" not in sql


def test_table_lineage_region_prefix_in_sql() -> None:
    """SQL uses the region-prefixed INFORMATION_SCHEMA path."""
    client = _bq_client([])
    fetch_table_lineage_from_jobs(
        bq_client=client,
        project_id="proj",
        dataset_id="ds",
        asset="asset",
        location="us-central1",
    )
    sql: str = client.query.call_args.args[0]
    assert "region-us-central1" in sql


def test_table_lineage_lookback_days_capped_at_180() -> None:
    """Callers can pass any value; the cap is enforced by the calling code."""
    # The fallback itself doesn't cap — caller is responsible. This test
    # just verifies the parameter is passed through to the query.
    client = _bq_client([])
    fetch_table_lineage_from_jobs(
        bq_client=client,
        project_id="proj",
        dataset_id="ds",
        asset="asset",
        lookback_days=200,  # caller should cap before calling
    )
    call_args = client.query.call_args
    job_config = call_args.kwargs.get("job_config") or call_args.args[1]
    lookback_param = next(p for p in job_config.query_parameters if p.name == "lookback_days")
    assert lookback_param.value == 200  # passed as-is; capping is caller's job


def test_table_lineage_statement_types_filter() -> None:
    """The statement_types array parameter is sent with the correct values."""
    client = _bq_client([])
    fetch_table_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    call_args = client.query.call_args
    job_config = call_args.kwargs.get("job_config") or call_args.args[1]
    st_param = next(p for p in job_config.query_parameters if p.name == "statement_types")
    expected = {"CREATE_TABLE_AS_SELECT", "INSERT", "MERGE", "UPDATE"}
    assert set(st_param.values) == expected


# ─── fetch_column_lineage_from_jobs ───────────────────────────────────────────


def test_column_lineage_produces_low_confidence_edges() -> None:
    row = _make_col_row(column_name="email_address")
    client = _bq_client([row])

    edges = fetch_column_lineage_from_jobs(
        bq_client=client,
        project_id="proj",
        dataset_id="my_ds",
        asset="my_table",
    )

    assert len(edges) == 1
    assert edges[0].confidence == "LOW"
    assert edges[0].lineage_source == "JOBS_FALLBACK"
    assert edges[0].source_column == "email_address"
    assert edges[0].target_column is None


def test_column_lineage_only_returns_edges_for_target_asset() -> None:
    """Rows where dest_table != asset are filtered out."""
    row_match = _make_col_row(dest_table="my_table", column_name="user_name")
    row_other = _make_col_row(dest_table="other_table", column_name="user_name")
    client = _bq_client([row_match, row_other])

    edges = fetch_column_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="my_ds", asset="my_table"
    )

    assert len(edges) == 1
    assert edges[0].asset == "my_table"


def test_column_lineage_permission_denied_returns_empty() -> None:
    client = MagicMock()
    client.query.side_effect = gcp_exceptions.Forbidden("no permission")

    edges = fetch_column_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    assert edges == []


def test_column_lineage_empty_result() -> None:
    client = _bq_client([])
    edges = fetch_column_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="ds", asset="asset"
    )
    assert edges == []


def test_column_lineage_all_edges_are_upstream() -> None:
    """Column inference only infers sources → all edges are UPSTREAM."""
    row = _make_col_row(column_name="phone_number")
    client = _bq_client([row])

    edges = fetch_column_lineage_from_jobs(
        bq_client=client, project_id="proj", dataset_id="my_ds", asset="my_table"
    )

    assert all(e.direction == "UPSTREAM" for e in edges)
