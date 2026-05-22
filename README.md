# Catalog Agent

A BigQuery-native **Data Catalog & Marketplace** with three capabilities:

1. **Data Catalog** — crawl `INFORMATION_SCHEMA` for any `(project_id, dataset_id)` and persist metadata to `catalog_registry.data_catalog_registry`.
2. **Data Lineage** — fetch upstream/downstream lineage via the Google Data Lineage API and write to `catalog_registry.lineage_registry`.
3. **Marketplace UI** — React + Vite app with cascading picker (project → dataset → asset → column) and an interactive lineage graph.

See [`Thoughts.md`](Thoughts.md) for the full spec and [`MILESTONES.md`](MILESTONES.md) for the build plan.

---

## Quickstart

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- Node 20+ and npm
- A GCP project with BigQuery enabled
- Application Default Credentials: `gcloud auth application-default login`

### 1. Clone and configure

```bash
git clone <repo-url>
cd metadata-catalog-agent
cp .env.example .env
# Edit .env: set GCP_PROJECT_ID at minimum
```

### 2. Backend

```bash
cd backend
uv sync --extra dev
uv run uvicorn catalog_agent.api.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health`

Expected output:
```json
{"status":"ok","gcp_project":"<your-project>","bq_reachable":true,"lineage_api_reachable":true}
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Opens http://localhost:5173
```

The page shows "Catalog Agent — coming soon" with a health badge in the top-right corner.

### 4. Run checks

```bash
# From repo root:
make lint        # ruff + black + eslint
make typecheck   # mypy + tsc
make test        # pytest + vitest
```

Or run them individually:

```bash
# Backend
cd backend
uv run ruff check src tests
uv run black --check src tests
uv run mypy src
uv run pytest -q

# Frontend
cd frontend
npm run lint
npm run typecheck
npm run test
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in the values. All variables have defaults that work for the default GCP project.

| Variable | Default | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `project-5c016d48-80d5-4534-b69` | GCP project hosting the catalog dataset |
| `CATALOG_DATASET` | `catalog_registry` | BigQuery dataset for registry tables |
| `GOOGLE_APPLICATION_CREDENTIALS` | _(ADC)_ | Path to service-account JSON (optional) |
| `LINEAGE_LOCATION` | `us` | Region for the Data Lineage API |
| `LINEAGE_FETCH_CONCURRENCY` | `4` | Max concurrent Lineage API calls |
| `JOBS_FALLBACK_LOOKBACK_DAYS` | `90` | Days of BQ job history to scan (max 180) |
| `ENABLE_JOBS_COLUMN_INFERENCE` | `0` | Enable LOW-confidence column edges from query text |
| `ENABLE_LLM_PII` | `0` | Enable LLM-based PII tagging (M07) |
| `API_KEY` | _(none)_ | Static API key for `X-API-Key` header; unset = no auth |

---

## Project layout

```
backend/        Python + FastAPI backend
frontend/       React + Vite + Tailwind frontend
infra/          Makefile, BQ DDL
docs/           Per-milestone documentation
.env.example    Environment variable template
```

---

## Integration tests (BigQuery)

Integration tests are gated by `BQ_INTEGRATION=1` and the `@pytest.mark.bq` marker. They hit a real BigQuery project and require valid credentials.

```bash
cd backend
BQ_INTEGRATION=1 uv run pytest -m bq -v
```
