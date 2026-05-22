"""CLI entry point for the data catalog crawler.

Usage:
    uv run python -m catalog_agent.catalog --project=<id> --dataset=<id>

Used by `make demo-m01 PROJECT=<id> DATASET=<id>`.
"""

import argparse

import structlog

from catalog_agent.bq.client import get_bq_client
from catalog_agent.bq.writer import merge_catalog_rows
from catalog_agent.catalog.crawler import crawl_dataset
from catalog_agent.config import get_settings

logger = structlog.get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl a BigQuery dataset into the catalog.")
    parser.add_argument("--project", required=True, help="GCP project ID to crawl")
    parser.add_argument("--dataset", required=True, help="Dataset ID to crawl")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl and print rows without writing to BQ",
    )
    args = parser.parse_args()

    settings = get_settings()
    bq_client = get_bq_client(settings)

    openai_client = None
    if settings.openai_api_key:
        from openai import OpenAI

        openai_client = OpenAI(api_key=settings.openai_api_key)
        print(f"OpenAI enrichment enabled (model: {settings.openai_model})")
    else:
        print("OpenAI key not set — using heuristic PII tagging only")

    print(f"Crawling {args.project}.{args.dataset} ...")
    rows = crawl_dataset(
        bq_client,
        args.project,
        args.dataset,
        openai_client=openai_client,
        openai_model=settings.openai_model,
    )

    tables = sum(1 for r in rows if r.asset_type in {"TABLE", "MATERIALIZED_VIEW", "EXTERNAL"})
    views = sum(1 for r in rows if r.asset_type == "VIEW")
    routines = sum(1 for r in rows if r.asset_type == "ROUTINE")
    pii_cols = sum(sum(1 for c in r.columns if c.is_pii) for r in rows)

    print(
        f"Found {len(rows)} assets: "
        f"{tables} tables, {views} views, {routines} routines. "
        f"{pii_cols} PII columns detected."
    )

    if args.dry_run:
        print("Dry-run mode — skipping write.")
        for row in rows:
            print(f"  {row.asset_type:<20} {row.dataset_id}.{row.asset}")
        return

    result = merge_catalog_rows(
        bq_client,
        rows,
        catalog_project_id=settings.gcp_project_id,
        catalog_dataset_id=settings.catalog_dataset,
    )
    print(
        f"Merge complete — inserted: {result.inserted}, "
        f"updated: {result.updated}, unchanged: {result.unchanged}"
    )


if __name__ == "__main__":
    main()
