.PHONY: lint typecheck test demo bq-init bq-init-lineage demo-m00 demo-m01 demo-m02 demo-m03

BACKEND_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../backend
FRONTEND_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../frontend

# ─── Code quality ────────────────────────────────────────────────────────────

lint:
	cd $(BACKEND_DIR) && uv run ruff check src tests
	cd $(BACKEND_DIR) && uv run black --check src tests
	cd $(FRONTEND_DIR) && npm run lint

typecheck:
	cd $(BACKEND_DIR) && uv run mypy src
	cd $(FRONTEND_DIR) && npm run typecheck

test:
	cd $(BACKEND_DIR) && uv run pytest -q -m "not bq"
	cd $(FRONTEND_DIR) && npm run test

# ─── Dev server ──────────────────────────────────────────────────────────────

demo:
	@echo "Starting backend on :8000 and frontend on :5173 ..."
	@trap 'kill 0' SIGINT; \
	cd $(BACKEND_DIR) && uv run uvicorn catalog_agent.api.main:app --reload --port 8000 & \
	cd $(FRONTEND_DIR) && npm run dev & \
	wait

# ─── BQ init (stub — tables are pre-created; DDL committed for reference) ────

bq-init:
	@echo "BQ init stub — catalog table already exists."
	@echo "Run 'make bq-init-lineage' after M02 to create lineage_registry."

bq-init-lineage:
	@test -n "$(PROJECT)" || (echo "Usage: make bq-init-lineage PROJECT=<gcp_project>"; exit 1)
	@SQL_FILE="$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/bq/lineage_registry.sql"; \
	SQL=$$(grep -Ev '^\s*--' "$$SQL_FILE"); \
	bq query --project_id="$(PROJECT)" --use_legacy_sql=false "$$SQL" \
	&& echo "lineage_registry table created (or already exists)."

# ─── Per-milestone demo targets ───────────────────────────────────────────────

demo-m00:
	@echo "M00 demo: health check"
	cd $(BACKEND_DIR) && uv run uvicorn catalog_agent.api.main:app --port 8000 & \
	sleep 2 && curl -s http://localhost:8000/health | python3 -m json.tool; \
	kill %1

demo-m01:
	@test -n "$(PROJECT)" || (echo "Usage: make demo-m01 PROJECT=<project_id> DATASET=<dataset_id>"; exit 1)
	@test -n "$(DATASET)" || (echo "Usage: make demo-m01 PROJECT=<project_id> DATASET=<dataset_id>"; exit 1)
	cd $(BACKEND_DIR) && uv run python -m catalog_agent.catalog --project=$(PROJECT) --dataset=$(DATASET)

demo-m02:
	@test -n "$(PROJECT)" || (echo "Usage: make demo-m02 PROJECT=<project_id> DATASET=<dataset_id>"; exit 1)
	@test -n "$(DATASET)" || (echo "Usage: make demo-m02 PROJECT=<project_id> DATASET=<dataset_id>"; exit 1)
	cd $(BACKEND_DIR) && uv run python -m catalog_agent.lineage --project=$(PROJECT) --dataset=$(DATASET)

demo-m03:
	@echo "demo-m03: implemented in M03"
