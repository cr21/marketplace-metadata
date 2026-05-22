"""Lineage fetcher: Lineage API primary + JOBS_BY_PROJECT fallback.

Public surface:
  - fetch_asset_lineage(client, asset_fqn, ...) -> list[LineageEdge]
  - fetch_column_lineage(client, asset_fqn, ...) -> list[LineageEdge]
  - fetch_lineage_for_dataset(...) -> LineageReport
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from google.cloud import bigquery, datacatalog_lineage_v1

from catalog_agent.config import Settings
from catalog_agent.lineage.client import LineageApiClient, make_asset_fqn
from catalog_agent.lineage.jobs_fallback import (
    fetch_column_lineage_from_jobs,
    fetch_table_lineage_from_jobs,
)
from catalog_agent.lineage.models import Direction, LineageEdge, LineageReport

logger = structlog.get_logger(__name__)


def _parse_timestamp(ts: object) -> datetime:
    """Convert a protobuf Timestamp (or datetime) to a UTC-aware datetime."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)
    try:
        return datetime.fromtimestamp(float(getattr(ts, "seconds", 0)), tz=UTC)
    except Exception:
        return datetime.now(UTC)


def fetch_asset_lineage(
    lineage_client: LineageApiClient,
    project_id: str,
    dataset_id: str,
    asset: str,
    asset_fqn: str,
) -> list[LineageEdge]:
    """Fetch UPSTREAM and DOWNSTREAM table-level edges from the Lineage API.

    Returns one LineageEdge per link, confidence="HIGH". Never raises.
    """
    fetched_at = datetime.now(UTC)
    edges: list[LineageEdge] = []

    for direction in ("UPSTREAM", "DOWNSTREAM"):
        links = lineage_client.search_links(asset_fqn, direction)
        for link in links:
            source_fqn = getattr(link.source, "fully_qualified_name", None)
            target_fqn = getattr(link.target, "fully_qualified_name", None)
            observed_at = fetched_at
            if hasattr(link, "start_time") and link.start_time:
                observed_at = _parse_timestamp(link.start_time)

            edges.append(
                LineageEdge(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    asset=asset,
                    asset_fqn=asset_fqn,
                    direction=direction,
                    source_fqn=source_fqn,
                    target_fqn=target_fqn,
                    source_column=None,
                    target_column=None,
                    process_name=None,
                    process_kind=None,
                    lineage_source="LINEAGE_API",
                    confidence="HIGH",
                    observed_at=observed_at,
                    fetched_at=fetched_at,
                )
            )

    return edges


def fetch_column_lineage(
    lineage_client: LineageApiClient,
    project_id: str,
    dataset_id: str,
    asset: str,
    asset_fqn: str,
    table_links: list[datacatalog_lineage_v1.Link],
) -> list[LineageEdge]:
    """Fetch column-level lineage from the Lineage API via BatchSearchLinkProcesses.

    Walks OpenLineage facets inside each ProcessLinks result to extract
    (source_column, target_column) pairs. Returns [] when not available.
    """
    if not table_links:
        return []

    # ProcessLinkInfo.link is a resource-name *string*, not a Link object.
    # Build a lookup so we can recover source/target FQNs for each link name.
    link_by_name = {lnk.name: lnk for lnk in table_links}

    fetched_at = datetime.now(UTC)
    process_links_list = lineage_client.batch_search_link_processes(table_links)
    edges: list[LineageEdge] = []

    for process_links in process_links_list:
        process_name = getattr(process_links, "process", None)
        process_kind: str | None = None

        for link_info in getattr(process_links, "links", []):
            # .link is a string (resource name), look up the original Link object
            link_name: str = getattr(link_info, "link", "") or ""
            link = link_by_name.get(link_name)
            if link is None:
                continue

            source_fqn: str | None = getattr(link.source, "fully_qualified_name", None)
            target_fqn: str | None = getattr(link.target, "fully_qualified_name", None)

            direction: Direction = (
                "UPSTREAM" if target_fqn and asset_fqn in target_fqn else "DOWNSTREAM"
            )

            observed_at = fetched_at
            # start_time lives on link_info (ProcessLinkInfo), not on the Link object
            start_time = getattr(link_info, "start_time", None) or getattr(link, "start_time", None)
            if start_time:
                observed_at = _parse_timestamp(start_time)

            col_pairs: list[tuple[str | None, str | None]] = []
            try:
                for facet_struct in getattr(link_info, "column_lineage_facets", []):
                    for field_transform in facet_struct.field_transform_facets:
                        output_field = field_transform.output_field
                        for input_field in field_transform.input_fields:
                            col_pairs.append(
                                (
                                    input_field.field if input_field.field else None,
                                    output_field.field if output_field else None,
                                )
                            )
            except (AttributeError, TypeError):
                pass

            if col_pairs:
                for src_col, tgt_col in col_pairs:
                    edges.append(
                        LineageEdge(
                            project_id=project_id,
                            dataset_id=dataset_id,
                            asset=asset,
                            asset_fqn=asset_fqn,
                            direction=direction,
                            source_fqn=source_fqn,
                            target_fqn=target_fqn,
                            source_column=src_col,
                            target_column=tgt_col,
                            process_name=str(process_name) if process_name else None,
                            process_kind=process_kind,  # type: ignore[arg-type]
                            lineage_source="LINEAGE_API",
                            confidence="HIGH",
                            observed_at=observed_at,
                            fetched_at=fetched_at,
                        )
                    )
            else:
                edges.append(
                    LineageEdge(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        asset=asset,
                        asset_fqn=asset_fqn,
                        direction=direction,
                        source_fqn=source_fqn,
                        target_fqn=target_fqn,
                        source_column=None,
                        target_column=None,
                        process_name=str(process_name) if process_name else None,
                        process_kind=process_kind,  # type: ignore[arg-type]
                        lineage_source="LINEAGE_API",
                        confidence="HIGH",
                        observed_at=observed_at,
                        fetched_at=fetched_at,
                    )
                )

    return edges


def _fetch_one_asset(
    lineage_client: LineageApiClient,
    bq_client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    asset: str,
    settings: Settings,
) -> list[LineageEdge]:
    """Fetch all lineage edges for a single asset (sync, runs in thread pool)."""
    asset_fqn = make_asset_fqn(project_id, dataset_id, asset)
    all_links: list[datacatalog_lineage_v1.Link] = []

    for raw_direction in ("UPSTREAM", "DOWNSTREAM"):
        all_links.extend(lineage_client.search_links(asset_fqn, raw_direction))

    table_edges = fetch_asset_lineage(lineage_client, project_id, dataset_id, asset, asset_fqn)
    col_edges = fetch_column_lineage(
        lineage_client, project_id, dataset_id, asset, asset_fqn, all_links
    )

    api_edges = table_edges + col_edges

    if api_edges:
        logger.info(
            "lineage_source_used",
            asset=asset,
            lineage_source_used="API",
            edge_count=len(api_edges),
        )
        return api_edges

    fallback_edges = fetch_table_lineage_from_jobs(
        bq_client=bq_client,
        project_id=project_id,
        dataset_id=dataset_id,
        asset=asset,
        location=settings.lineage_location,
        lookback_days=min(settings.jobs_fallback_lookback_days, 180),
    )

    if settings.enable_jobs_column_inference:
        col_fallback = fetch_column_lineage_from_jobs(
            bq_client=bq_client,
            project_id=project_id,
            dataset_id=dataset_id,
            asset=asset,
            location=settings.lineage_location,
            lookback_days=min(settings.jobs_fallback_lookback_days, 180),
        )
        fallback_edges.extend(col_fallback)

    source_used = "FALLBACK" if fallback_edges else "NONE"
    logger.info(
        "lineage_source_used",
        asset=asset,
        lineage_source_used=source_used,
        edge_count=len(fallback_edges),
    )
    return fallback_edges


async def fetch_lineage_for_dataset(
    lineage_client: LineageApiClient,
    bq_client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    assets: list[str],
    settings: Settings,
) -> LineageReport:
    """Fetch lineage for all assets in a dataset with bounded concurrency.

    Uses asyncio.Semaphore to cap concurrent Lineage API calls at
    settings.lineage_fetch_concurrency (default 4).

    Args:
        lineage_client: Pre-constructed LineageApiClient.
        bq_client: BigQuery client for the JOBS fallback.
        project_id: GCP project ID of the crawled dataset.
        dataset_id: Dataset name.
        assets: List of asset names to fetch lineage for.
        settings: Application settings.

    Returns:
        LineageReport with all collected edges.
    """
    sem = asyncio.Semaphore(settings.lineage_fetch_concurrency)
    report = LineageReport(project_id=project_id, dataset_id=dataset_id)

    async def _fetch(asset: str) -> list[LineageEdge]:
        async with sem:
            return await asyncio.to_thread(
                _fetch_one_asset,
                lineage_client,
                bq_client,
                project_id,
                dataset_id,
                asset,
                settings,
            )

    results = await asyncio.gather(*[_fetch(a) for a in assets], return_exceptions=True)

    for asset, result in zip(assets, results, strict=True):
        if isinstance(result, BaseException):
            logger.error("lineage_fetch_asset_error", asset=asset, error=str(result))
        else:
            report.edges.extend(result)

    logger.info(
        "fetch_lineage_for_dataset_done",
        project_id=project_id,
        dataset_id=dataset_id,
        asset_count=len(assets),
        summary=report.summary(),
    )
    return report
