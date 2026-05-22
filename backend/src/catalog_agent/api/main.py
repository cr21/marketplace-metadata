"""FastAPI application entry point."""

import asyncio
import json
import re
import threading
from pathlib import Path
from typing import Any, Callable

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from catalog_agent.bq.client import get_bq_client
from catalog_agent.bq.writer import merge_catalog_rows
from catalog_agent.catalog.crawler import crawl_dataset
from catalog_agent.config import Settings, get_settings

logger = structlog.get_logger()

app = FastAPI(
    title="Catalog Agent",
    description="Data Catalog & Marketplace Agent for BigQuery",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Registry table DDL — loaded from the single source of truth in infra/
# ---------------------------------------------------------------------------

# main.py lives at backend/src/catalog_agent/api/main.py → parents[4] = project root
_DDL_FILE = Path(__file__).parents[4] / "infra" / "bq" / "data_catalog_registry.sql"


def _registry_ddl(project: str, dataset: str, table: str) -> str:
    """Return CREATE OR REPLACE TABLE DDL targeting the given project.dataset.table.

    Reads the canonical schema from infra/bq/data_catalog_registry.sql, strips
    comment lines and the trailing semicolon, then rewrites the CREATE statement
    to target the caller's destination.
    """
    raw = _DDL_FILE.read_text()
    body_lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
    body = "\n".join(body_lines).strip().rstrip(";")
    return re.sub(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`[^`]+`",
        f"CREATE OR REPLACE TABLE `{project}.{dataset}.{table}`",
        body,
        flags=re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    gcp_project: str
    bq_reachable: bool
    lineage_api_reachable: bool


def _check_bq(settings: Settings) -> bool:
    try:
        client = get_bq_client(settings)
        list(client.list_projects(max_results=1))
        return True
    except Exception:
        logger.warning("bq_health_check_failed")
        return False


def _check_lineage_api(settings: Settings) -> bool:
    try:
        from google.cloud import datacatalog_lineage_v1

        client = datacatalog_lineage_v1.LineageClient()
        parent = f"projects/{settings.gcp_project_id}/locations/{settings.lineage_location}"
        request = datacatalog_lineage_v1.ListProcessesRequest(parent=parent, page_size=1)
        client.list_processes(request=request)
        return True
    except Exception:
        logger.warning("lineage_api_health_check_failed")
        return False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        gcp_project=settings.gcp_project_id,
        bq_reachable=_check_bq(settings),
        lineage_api_reachable=_check_lineage_api(settings),
    )


# ---------------------------------------------------------------------------
# Dataset listing
# ---------------------------------------------------------------------------

class DatasetListResponse(BaseModel):
    project_id: str
    datasets: list[str]


@app.get("/api/datasets", response_model=DatasetListResponse)
def list_datasets(project_id: str = Query(..., description="GCP project ID")) -> DatasetListResponse:
    settings = get_settings()
    try:
        client = get_bq_client(settings)
        dataset_refs = list(client.list_datasets(project=project_id))
        datasets = [f"{project_id}:{ds.dataset_id}" for ds in dataset_refs]
        return DatasetListResponse(project_id=project_id, datasets=datasets)
    except Exception as e:
        logger.warning("list_datasets_failed", project_id=project_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Catalog build (SSE streaming)
# ---------------------------------------------------------------------------

class BuildCatalogRequest(BaseModel):
    source_project_id: str
    source_dataset_id: str   # dataset name only, no "project:" prefix
    registry_project: str
    registry_dataset: str    # dataset name only
    registry_table: str = "data_catalog_registry"


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _do_build(req: BuildCatalogRequest, emit: Callable[[dict[str, Any]], None]) -> None:
    """Run the full catalog build synchronously, emitting SSE events throughout."""
    settings = get_settings()
    client = get_bq_client(settings)
    source_label = f"{req.source_project_id}:{req.source_dataset_id}"
    registry_label = f"{req.registry_project}.{req.registry_dataset}.{req.registry_table}"

    emit({"type": "activity", "text": f"Building catalog for {source_label}", "event_type": "info"})
    emit({"type": "activity", "text": f"Registry destination: {registry_label}", "event_type": "info"})
    emit({"type": "status", "text": "Ensuring registry table exists"})
    emit({"type": "activity", "text": "Ensuring registry table exists", "event_type": "info"})

    # Create (or replace) registry table using canonical schema from infra/
    ddl = _registry_ddl(req.registry_project, req.registry_dataset, req.registry_table)
    emit({
        "type": "activity",
        "text": f"TOOL execute_sql(..., query=CREATE TABLE IF NOT EXISTS `{registry_label}`...)",
        "event_type": "tool",
    })
    client.query(ddl).result()

    # Read INFORMATION_SCHEMA
    emit({"type": "status", "text": f"Reading INFORMATION_SCHEMA for {source_label}..."})
    emit({"type": "progress", "step": "Reading INFORMATION_SCHEMA", "current": 0, "total": 1})
    emit({"type": "activity", "text": f"Reading columns from {req.source_dataset_id}", "event_type": "info"})
    emit({
        "type": "activity",
        "text": f"TOOL execute_sql_readonly(..., query=SELECT table_name, column_name, data_type, ordinal_position FROM `{req.source_project_id}.{req.source_dataset_id}...`)",
        "event_type": "tool",
    })
    emit({"type": "activity", "text": f"Reading table types from {req.source_dataset_id}", "event_type": "info"})
    emit({
        "type": "activity",
        "text": f"TOOL execute_sql_readonly(..., query=SELECT table_name, table_type FROM `{req.source_project_id}.{req.source_dataset_id}...`)",
        "event_type": "tool",
    })

    rows = crawl_dataset(client, req.source_project_id, req.source_dataset_id)

    # Skip the registry table itself if it lives in the same dataset
    filtered_rows = [
        r for r in rows
        if not (r.dataset_id == req.registry_dataset and r.asset == req.registry_table)
    ]
    if len(filtered_rows) < len(rows):
        emit({"type": "activity", "text": f"Skipping registry table itself ({req.registry_table})", "event_type": "info"})

    total_assets = len(filtered_rows)
    total_cols = sum(len(r.columns) for r in filtered_rows)
    emit({"type": "progress", "step": "Reading INFORMATION_SCHEMA", "current": 1, "total": 1})
    emit({"type": "activity", "text": f"Crawl complete: {total_assets} table(s), {total_cols} column(s) in {req.source_dataset_id}", "event_type": "success"})
    emit({"type": "stats", "datasets": 1, "assets": total_assets})

    # LLM enrichment — runs only when OPENAI_API_KEY is set in the environment
    if settings.openai_api_key:
        try:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.openai_api_key)
            emit({"type": "status", "text": "Generating metadata with LLM…"})
            enriched = []
            for i, row in enumerate(filtered_rows):
                emit({
                    "type": "activity",
                    "text": f"Generating metadata for {row.dataset_id}.{row.asset}",
                    "event_type": "info",
                })
                emit({"type": "progress", "step": "Generating metadata", "current": i, "total": total_assets})
                from catalog_agent.catalog.llm_enricher import enrich_catalog_row
                enriched.append(enrich_catalog_row(row, openai_client, settings.openai_model))
            filtered_rows = enriched
            emit({"type": "progress", "step": "Generating metadata", "current": total_assets, "total": total_assets})
            emit({"type": "activity", "text": "LLM enrichment complete", "event_type": "success"})
        except Exception as e:
            emit({"type": "activity", "text": f"LLM enrichment skipped: {e}", "event_type": "info"})
            emit({"type": "progress", "step": "Generating metadata", "current": total_assets, "total": max(total_assets, 1)})
    else:
        emit({"type": "activity", "text": "LLM enrichment skipped (no OPENAI_API_KEY set)", "event_type": "info"})
        emit({"type": "progress", "step": "Generating metadata", "current": total_assets, "total": max(total_assets, 1)})

    for row in filtered_rows:
        emit({"type": "activity", "text": f"Writing {req.source_dataset_id}.{row.asset}", "event_type": "info"})

    emit({"type": "status", "text": "Writing to BigQuery…"})
    emit({"type": "progress_write", "step": "Written to BigQuery", "current": 0, "total": max(total_assets, 1)})
    emit({"type": "activity", "text": "…awaiting BigQuery (15s)", "event_type": "info"})

    result = merge_catalog_rows(
        client=client,
        rows=filtered_rows,
        catalog_project_id=req.registry_project,
        catalog_dataset_id=req.registry_dataset,
        table_id=req.registry_table,
    )

    rows_written = result.inserted + result.updated
    emit({"type": "progress_write", "step": "Written to BigQuery", "current": rows_written, "total": max(total_assets, 1)})
    emit({
        "type": "activity",
        "text": f"TOOL execute_sql(..., query=INSERT INTO `{registry_label}`...)",
        "event_type": "tool",
    })
    emit({"type": "activity", "text": f"Catalog build complete: {rows_written} row(s) in {registry_label}", "event_type": "success"})

    emit({
        "type": "done",
        "rows_written": rows_written,
        "registry_path": registry_label,
        "rows": [
            {
                "project_id": r.project_id,
                "dataset_id": r.dataset_id,
                "asset": r.asset,
                "asset_type": r.asset_type,
                "column_count": len(r.columns),
                "table_metadata": r.table_metadata,
                "columns": [c.model_dump() for c in r.columns],
            }
            for r in filtered_rows
        ],
    })


# ---------------------------------------------------------------------------
# Catalog update (incremental, SSE streaming)
# ---------------------------------------------------------------------------

class UpdateCatalogRequest(BaseModel):
    source_project_id: str
    source_dataset_id: str   # dataset name only, no "project:" prefix


def _compute_delta(
    crawled: list,
    existing: dict,
) -> tuple[list, list, list]:
    """Split crawled CatalogRows into (new_rows, changed_rows, unchanged_rows).

    Mirrors the MERGE SQL comparison exactly: only column names and data_types
    are compared (sorted order-independent).  Descriptions, is_pii, and all
    table_metadata fields are intentionally excluded so that:
      - LLM-enriched descriptions stored during BUILD never cause false updates
      - Volatile fields (row_count, timestamps) never cause false updates
      - Only real structural schema changes trigger a delta
    """
    import json as _json

    new_rows: list = []
    changed_rows: list = []
    unchanged_rows: list = []

    for row in crawled:
        key = (row.project_id, row.dataset_id, row.asset)
        if key not in existing:
            new_rows.append(row)
            continue

        ex = existing[key]

        # Build name→data_type maps (order-independent, description-free)
        new_schema: dict[str, str] = {c.name: c.data_type for c in row.columns}

        try:
            ex_cols_raw = _json.loads(ex.get("columns_json") or "[]")
            ex_schema: dict[str, str] = {
                c["name"]: c["data_type"]
                for c in ex_cols_raw
                if isinstance(c, dict) and c.get("name") and c.get("data_type")
            }
        except Exception:
            # If we can't parse the stored columns, treat as unchanged to avoid
            # false positives — a genuine schema change will still surface on
            # the next run once the registry is consistent.
            unchanged_rows.append(row)
            continue

        schema_changed = (
            set(new_schema.keys()) != set(ex_schema.keys())
            or any(new_schema[name] != ex_schema.get(name) for name in new_schema)
        )

        if schema_changed:
            changed_rows.append(row)
        else:
            unchanged_rows.append(row)

    return new_rows, changed_rows, unchanged_rows


def _do_update(req: UpdateCatalogRequest, emit: Callable[[dict[str, Any]], None]) -> None:
    """Run the incremental catalog update synchronously, emitting SSE events."""
    from catalog_agent.bq.reader import read_registry_snapshot, registry_table_exists

    settings = get_settings()
    client = get_bq_client(settings)

    registry_project = req.source_project_id
    registry_dataset = req.source_dataset_id
    registry_table = "data_catalog_registry"
    registry_label = f"{registry_project}.{registry_dataset}.{registry_table}"
    source_label = f"{req.source_project_id}:{req.source_dataset_id}"

    emit({"type": "activity", "text": f"Updating catalog for {source_label}", "event_type": "info"})
    emit({"type": "activity", "text": f"Registry table: {registry_label}", "event_type": "info"})
    emit({"type": "activity", "text": "Update scope: incremental (new + changed assets only)", "event_type": "info"})

    # ── Check / create registry table ────────────────────────────────────────
    table_exists = registry_table_exists(client, registry_project, registry_dataset, registry_table)

    if not table_exists:
        emit({"type": "activity", "text": "Registry table not found — will create and populate", "event_type": "info"})
        emit({"type": "status", "text": "Creating registry table…"})
        emit({
            "type": "activity",
            "text": f"TOOL execute_sql(..., query=CREATE TABLE `{registry_label}`...)",
            "event_type": "tool",
        })
        ddl = _registry_ddl(registry_project, registry_dataset, registry_table)
        client.query(ddl).result()
        existing_snapshot: dict = {}
    else:
        # ── Read existing registry rows ───────────────────────────────────────
        emit({"type": "activity", "text": "Reading existing assets from registry", "event_type": "info"})
        emit({"type": "status", "text": "Reading existing registry…"})
        emit({
            "type": "activity",
            "text": f"TOOL execute_sql_readonly(..., query=SELECT * FROM `{registry_label}`)",
            "event_type": "tool",
        })
        snapshot = read_registry_snapshot(client, registry_project, registry_dataset, registry_table)
        existing_snapshot = snapshot if snapshot is not None else {}
        emit({
            "type": "activity",
            "text": f"Loaded {len(existing_snapshot)} existing asset(s) from registry",
            "event_type": "info",
        })

    # ── Crawl INFORMATION_SCHEMA ─────────────────────────────────────────────
    emit({"type": "status", "text": f"Reading INFORMATION_SCHEMA for {source_label}…"})
    emit({"type": "progress", "step": "Reading INFORMATION_SCHEMA", "current": 0, "total": 1})
    emit({"type": "activity", "text": f"Reading INFORMATION_SCHEMA for {req.source_dataset_id}", "event_type": "info"})
    emit({
        "type": "activity",
        "text": (
            f"TOOL execute_sql_readonly(..., query=SELECT * FROM "
            f"`{req.source_project_id}.{req.source_dataset_id}.INFORMATION_SCHEMA.COLUMNS`)"
        ),
        "event_type": "tool",
    })

    all_rows = crawl_dataset(client, req.source_project_id, req.source_dataset_id)
    all_rows = [r for r in all_rows if not (r.dataset_id == registry_dataset and r.asset == registry_table)]

    emit({"type": "progress", "step": "Reading INFORMATION_SCHEMA", "current": 1, "total": 1})
    emit({
        "type": "activity",
        "text": f"Crawl complete: {len(all_rows)} asset(s) discovered in {req.source_dataset_id}",
        "event_type": "success",
    })
    emit({"type": "stats", "datasets": 1, "assets": len(all_rows)})

    # ── Diff ─────────────────────────────────────────────────────────────────
    emit({"type": "activity", "text": "Diffing metadata against registry…", "event_type": "info"})
    emit({"type": "status", "text": "Comparing metadata…"})

    new_rows, changed_rows, unchanged_rows = _compute_delta(all_rows, existing_snapshot)
    delta_rows = new_rows + changed_rows
    new_asset_names = {r.asset for r in new_rows}

    emit({
        "type": "activity",
        "text": (
            f"Diff complete: {len(new_rows)} new, "
            f"{len(changed_rows)} modified, "
            f"{len(unchanged_rows)} unchanged"
        ),
        "event_type": "info",
    })

    if not delta_rows:
        emit({"type": "activity", "text": "Registry already has all assets", "event_type": "info"})
        emit({"type": "activity", "text": "Nothing new to add", "event_type": "info"})
        emit({"type": "activity", "text": "Update completed successfully", "event_type": "success"})
        emit({
            "type": "done",
            "rows_written": 0,
            "inserted": 0,
            "updated": 0,
            "registry_path": registry_label,
            "no_changes": True,
            "rows": [],
        })
        return

    # ── LLM enrichment for delta rows ────────────────────────────────────────
    if settings.openai_api_key:
        try:
            from openai import OpenAI
            from catalog_agent.catalog.llm_enricher import enrich_catalog_row

            openai_client = OpenAI(api_key=settings.openai_api_key)
            emit({"type": "status", "text": "Generating metadata with LLM…"})
            enriched = []
            for i, row in enumerate(delta_rows):
                emit({
                    "type": "activity",
                    "text": f"Generating metadata for {row.dataset_id}.{row.asset}",
                    "event_type": "info",
                })
                emit({"type": "progress", "step": "Generating metadata", "current": i, "total": len(delta_rows)})
                enriched.append(enrich_catalog_row(row, openai_client, settings.openai_model))
            delta_rows = enriched
            emit({"type": "progress", "step": "Generating metadata", "current": len(delta_rows), "total": len(delta_rows)})
            emit({"type": "activity", "text": "LLM enrichment complete", "event_type": "success"})
        except Exception as e:
            emit({"type": "activity", "text": f"LLM enrichment skipped: {e}", "event_type": "info"})
    else:
        emit({"type": "activity", "text": "LLM enrichment skipped (no OPENAI_API_KEY set)", "event_type": "info"})

    # ── Write delta rows ─────────────────────────────────────────────────────
    emit({"type": "status", "text": "Writing changes to BigQuery…"})
    emit({"type": "progress_write", "step": "Writing to BigQuery", "current": 0, "total": len(delta_rows)})

    for row in delta_rows:
        change_label = "new" if row.asset in new_asset_names else "modified"
        emit({
            "type": "activity",
            "text": f"Writing {req.source_dataset_id}.{row.asset} [{change_label}]",
            "event_type": "info",
        })

    emit({"type": "activity", "text": "…awaiting BigQuery", "event_type": "info"})
    emit({
        "type": "activity",
        "text": f"TOOL execute_sql(..., query=MERGE `{registry_label}`...)",
        "event_type": "tool",
    })

    result = merge_catalog_rows(
        client=client,
        rows=delta_rows,
        catalog_project_id=registry_project,
        catalog_dataset_id=registry_dataset,
        table_id=registry_table,
    )

    rows_written = result.inserted + result.updated
    emit({"type": "progress_write", "step": "Writing to BigQuery", "current": rows_written, "total": len(delta_rows)})
    emit({
        "type": "activity",
        "text": (
            f"Update complete: {result.inserted} inserted, "
            f"{result.updated} updated in {registry_label}"
        ),
        "event_type": "success",
    })

    emit({
        "type": "done",
        "rows_written": rows_written,
        "inserted": result.inserted,
        "updated": result.updated,
        "registry_path": registry_label,
        "no_changes": False,
        "rows": [
            {
                "project_id": r.project_id,
                "dataset_id": r.dataset_id,
                "asset": r.asset,
                "asset_type": r.asset_type,
                "column_count": len(r.columns),
                "table_metadata": r.table_metadata,
                "columns": [c.model_dump() for c in r.columns],
                "change_type": "new" if r.asset in new_asset_names else "modified",
            }
            for r in delta_rows
        ],
    })


@app.post("/api/catalog/update")
async def update_catalog(req: UpdateCatalogRequest) -> StreamingResponse:
    """Stream incremental catalog update progress as Server-Sent Events."""

    async def event_stream() -> Any:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def worker() -> None:
            try:
                _do_update(req, emit)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "text": str(exc)},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            event = await queue.get()
            if event is None:
                break
            yield _sse(event)
            await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/catalog/build")
async def build_catalog(req: BuildCatalogRequest) -> StreamingResponse:
    """Stream catalog build progress as Server-Sent Events."""

    async def event_stream() -> Any:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()  # use get_running_loop inside async context

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def worker() -> None:
            try:
                _do_build(req, emit)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "text": str(exc)},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            event = await queue.get()
            if event is None:
                break
            yield _sse(event)
            await asyncio.sleep(0)  # yield to event loop so uvicorn flushes each chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
