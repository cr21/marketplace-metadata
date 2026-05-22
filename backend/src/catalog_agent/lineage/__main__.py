"""CLI entry point for the M02 lineage demo: python -m catalog_agent.lineage.

Usage:
    uv run python -m catalog_agent.lineage --project=<p> --dataset=<d>
"""

import argparse
import asyncio
import sys

import structlog

from catalog_agent.bq.client import get_bq_client
from catalog_agent.config import get_settings
from catalog_agent.lineage.client import LineageApiClient
from catalog_agent.lineage.fetcher import fetch_lineage_for_dataset
from catalog_agent.lineage.writer import merge_lineage_report

logger = structlog.get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and write lineage for a BQ dataset.")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset ID")
    return parser.parse_args()


async def _run(project: str, dataset: str) -> None:
    settings = get_settings()
    bq_client = get_bq_client(settings)

    # List assets from the catalog registry so we know what to fetch lineage for
    query = f"""
        SELECT DISTINCT asset
        FROM `{settings.gcp_project_id}.{settings.catalog_dataset}.data_catalog_registry`
        WHERE project_id = @project_id AND dataset_id = @dataset_id
    """
    from google.cloud import bigquery as bq_lib

    job_config = bq_lib.QueryJobConfig(
        query_parameters=[
            bq_lib.ScalarQueryParameter("project_id", "STRING", project),
            bq_lib.ScalarQueryParameter("dataset_id", "STRING", dataset),
        ]
    )
    rows = list(bq_client.query(query, job_config=job_config).result())
    assets = [r.asset for r in rows]

    if not assets:
        print(
            f"No catalog rows found for {project}.{dataset}. Run 'make demo-m01' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Fetching lineage for {len(assets)} asset(s) in {project}.{dataset} ...")

    lineage_client = LineageApiClient(
        project_id=project,
        location=settings.lineage_location,
    )

    report = await fetch_lineage_for_dataset(
        lineage_client=lineage_client,
        bq_client=bq_client,
        project_id=project,
        dataset_id=dataset,
        assets=assets,
        settings=settings,
    )

    print(report.summary())

    if report.edges:
        result = merge_lineage_report(
            client=bq_client,
            report=report,
            catalog_project_id=settings.gcp_project_id,
            catalog_dataset_id=settings.catalog_dataset,
        )
        print(f"{result.inserted} written, {result.unchanged} unchanged.")
    else:
        print("0 written.")


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.project, args.dataset))


if __name__ == "__main__":
    main()
