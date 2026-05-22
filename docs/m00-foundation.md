# M00 — Foundation

**Status:** DONE | **Completed:** 2026-05-20

---

## What was built

Repo skeleton so every subsequent milestone can `uv run` and `npm run dev` from a fresh clone.

### Backend

| File | Purpose |
|---|---|
| `backend/pyproject.toml` | uv-managed project; runtime + dev deps pinned |
| `backend/src/catalog_agent/config.py` | `Settings` (pydantic-settings); reads all env vars |
| `backend/src/catalog_agent/bq/client.py` | `get_bq_client()` — ADC or service-account JSON |
| `backend/src/catalog_agent/api/main.py` | FastAPI app + `GET /health` |
| `backend/tests/unit/test_health.py` | 3 unit tests for `/health` (mocked BQ + Lineage) |

### Frontend

| File | Purpose |
|---|---|
| `frontend/package.json` | Vite + React 18 + TS + Tailwind + Vitest |
| `frontend/src/App.tsx` | Stub page + health badge (polls `/health`) |
| `frontend/src/__tests__/App.test.tsx` | 4 component tests (connected / unavailable / error) |

### Infra

| File | Purpose |
|---|---|
| `infra/Makefile` | `lint`, `typecheck`, `test`, `demo`, `bq-init`, per-milestone demo stubs |
| `Makefile` | Root-level shim delegating to `infra/Makefile` |
| `.github/workflows/ci.yml` | CI: backend (ruff, black, mypy, pytest) + frontend (eslint, tsc, vitest) |
| `.env.example` | All env vars documented with defaults and explanations |
| `README.md` | Quickstart, env var table, integration test instructions |

---

## Key decisions

- `Settings` is a single flat pydantic-settings class — no nesting. Fields are optional with sensible defaults so the health check works without credentials in test environments.
- `/health` catches all exceptions from BQ and Lineage API probes — it always returns 200 with `bq_reachable: bool`. A 500 here would break the frontend badge.
- The Vite dev server proxies `/health` and `/api` to `:8000`, so the frontend never needs a hardcoded backend URL.
- `node_modules` excluded from git via `.gitignore`.

---

## Running

```bash
# Backend
cd backend
uv sync --extra dev
uv run uvicorn catalog_agent.api.main:app --reload --port 8000
curl http://localhost:8000/health

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# http://localhost:5173

# Both at once (from repo root)
make demo
```

## Checks

```bash
make lint       # ruff + black --check + eslint
make typecheck  # mypy + tsc
make test       # pytest (not bq) + vitest
```
