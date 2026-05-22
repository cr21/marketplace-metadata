# M02 — Data Lineage Fetcher + Writer

Fetches upstream/downstream lineage for BigQuery assets and persists it into
`catalog_registry.lineage_registry`. Two sources: the Google Data Lineage API
(primary, `HIGH` confidence) and `INFORMATION_SCHEMA.JOBS_BY_PROJECT` (fallback,
`MEDIUM`/`LOW` confidence).

---

## 1. Schema — `lineage_registry`

```
project_id     STRING  NOT NULL   GCP project ID of the crawled asset
dataset_id     STRING  NOT NULL   BigQuery dataset
asset          STRING  NOT NULL   Asset name (table, view, routine)
asset_fqn      STRING  NOT NULL   project.dataset.asset
direction      STRING  NOT NULL   UPSTREAM | DOWNSTREAM
source_fqn     STRING             FQN of the source side of the edge
target_fqn     STRING             FQN of the target side of the edge
source_column  STRING             Source column; NULL for table-level edges
target_column  STRING             Target column; NULL for table-level edges
process_name   STRING             Lineage API process resource (NULL for JOBS_FALLBACK)
process_kind   STRING             BIGQUERY_JOB | DATAFLOW_JOB | JOBS_HISTORY
lineage_source STRING  NOT NULL   LINEAGE_API | JOBS_FALLBACK
confidence     STRING  NOT NULL   HIGH | MEDIUM | LOW
observed_at    TIMESTAMP NOT NULL When the lineage event was observed
fetched_at     TIMESTAMP NOT NULL When this row was written
```

**Primary key** (for MERGE idempotency):
```
(project_id, dataset_id, asset, direction, source_fqn, target_fqn,
 source_column, target_column, lineage_source)
```

NULL values participate in the key via `IS NOT DISTINCT FROM` in the MERGE statement.
Including `lineage_source` in the key means an edge confirmed by both the Lineage API
and JOBS fallback keeps both rows — the UI prefers `LINEAGE_API` rows.

---

## 2. Confidence tiers

| Tier | Source | When used | UI default |
|------|--------|-----------|------------|
| `HIGH` | Google Data Lineage API | Always (when API returns edges) | Shown |
| `MEDIUM` | `JOBS_BY_PROJECT` table-level | API returned zero edges for the asset | Shown |
| `LOW` | `JOBS_BY_PROJECT` column inference | `ENABLE_JOBS_COLUMN_INFERENCE=1` | **Hidden** (toggle to reveal) |

---

## 3. Fetcher flow

For each asset in a dataset:

1. Call `SearchLinks(target=asset_fqn)` → UPSTREAM edges.
2. Call `SearchLinks(source=asset_fqn)` → DOWNSTREAM edges.
3. Call `BatchSearchLinkProcesses(links=[...])` → column-level facets.
4. If total API edges > 0: use `lineage_source="LINEAGE_API"`, `confidence="HIGH"`. Stop.
5. Else: call `fetch_table_lineage_from_jobs(...)` → `lineage_source="JOBS_FALLBACK"`, `confidence="MEDIUM"`.
6. If `ENABLE_JOBS_COLUMN_INFERENCE=1`: additionally call `fetch_column_lineage_from_jobs(...)` → `confidence="LOW"`.

Concurrency is bounded by `LINEAGE_FETCH_CONCURRENCY` (default 4) via `asyncio.Semaphore`.
Each asset fetch runs in a thread pool (`asyncio.to_thread`) because the BQ and Lineage API
clients are synchronous.

---

## 4. JOBS fallback — design and constraints

### Statement types

Only these statement types produce lineage we care about:
```
CREATE_TABLE_AS_SELECT, INSERT, MERGE, UPDATE
```

`SELECT` and `DELETE` are excluded — they don't write data or the writes don't
create meaningful downstream lineage.

### Filters always applied

- `state = 'DONE'`
- `error_result IS NULL`
- `creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)`

### Region scoping

`INFORMATION_SCHEMA.JOBS_BY_PROJECT` is **region-scoped**. The query uses:
```sql
`region-{location}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
```

Querying the wrong region returns empty results, not an error. Use the dataset's
`LINEAGE_LOCATION` setting (default `us`).

### Permission requirement

`bigquery.jobs.listAll` is required on the project. If the caller lacks this permission,
the fallback catches the `Forbidden` exception, logs a warning, and returns `[]`. The
overall fetch continues without failing.

### Lookback cap

BQ retains `JOBS_BY_PROJECT` for 180 days. Default lookback: 90 days. Max: 180 days.
The fetcher enforces this cap: `min(settings.jobs_fallback_lookback_days, 180)`.

---

## 5. JOBS column inference (LOW confidence) — caveats

Enabled by `ENABLE_JOBS_COLUMN_INFERENCE=1`. Uses a `LIKE '%column_name%'` substring
match against the query text. **This is intentionally LOW confidence with known false positives:**

| Failure mode | Example |
|---|---|
| Column name is substring of another identifier | `id` matches `paid`, `void`, `width` |
| Aliased columns | `SELECT a AS user_id` → edge from `a`, not `user_id` |
| Columns in WHERE/ORDER BY/GROUP BY | Attributed as source even if not selected |
| String literals and comments | `SELECT 'email' FROM t` matches a column named `email` |
| Shared column names across tables | All matching source columns get attributed to all matching targets |

**Mitigation:** column names shorter than 3 characters are excluded by the SQL query
(`LENGTH(column_name) >= 3`). This removes `id`, `dt`, `n`, etc. but doesn't eliminate
all false positives.

The UI hides `LOW` edges by default behind a "Show inferred edges" toggle with a
dashed line style and tooltip warning.

When proper SQL-parsed lineage (via `sqlglot` AST) ships in a future milestone,
`LOW` edges from `JOBS_FALLBACK` will be deprecated with a one-line `DELETE` migration.

---

## 6. Writer — idempotent MERGE

One BQ call per dataset (single MERGE over an UNNEST of a JSON array parameter).

The MERGE key handles NULL columns via `IS NOT DISTINCT FROM`:
```sql
AND target.source_column IS NOT DISTINCT FROM source.source_column
AND target.target_column IS NOT DISTINCT FROM source.target_column
```

No UPDATE clause — duplicate edges are simply not re-inserted. Re-running on
unchanged data yields `inserted=0`.

---

## 7. Environment variables

| Variable | Default | Description |
|---|---|---|
| `LINEAGE_LOCATION` | `us` | Lineage API + JOBS region (must match dataset) |
| `LINEAGE_FETCH_CONCURRENCY` | `4` | Max concurrent Lineage API calls per dataset |
| `JOBS_FALLBACK_LOOKBACK_DAYS` | `90` | Days of JOBS history to scan (max 180) |
| `ENABLE_JOBS_COLUMN_INFERENCE` | `false` | Enable LOW-confidence column edge inference |

---

## 8. Usage

### Create the table

```bash
make bq-init-lineage PROJECT=<gcp_project>
```

### Run the demo

```bash
# First crawl the catalog if not already done:
make demo-m01 PROJECT=my-project DATASET=my_dataset

# Then fetch lineage:
make demo-m02 PROJECT=my-project DATASET=my_dataset
```

### Programmatic usage

```python
import asyncio
from catalog_agent.bq.client import get_bq_client
from catalog_agent.config import get_settings
from catalog_agent.lineage.client import LineageApiClient
from catalog_agent.lineage.fetcher import fetch_lineage_for_dataset
from catalog_agent.lineage.writer import merge_lineage_report

settings = get_settings()
bq_client = get_bq_client(settings)
lineage_client = LineageApiClient(
    project_id="my-project",
    location=settings.lineage_location,
)

report = asyncio.run(fetch_lineage_for_dataset(
    lineage_client=lineage_client,
    bq_client=bq_client,
    project_id="my-project",
    dataset_id="my_dataset",
    assets=["orders", "customers"],
    settings=settings,
))

print(report.summary())
# → "12 edges fetched (HIGH: 8, MEDIUM: 4, LOW: 0)"

result = merge_lineage_report(
    client=bq_client,
    report=report,
    catalog_project_id=settings.gcp_project_id,
    catalog_dataset_id=settings.catalog_dataset,
)
print(f"{result.inserted} written, {result.unchanged} unchanged")
```

### Example output (lineage_registry row)

```json
{
  "project_id": "my-project",
  "dataset_id": "sales",
  "asset": "orders_summary",
  "asset_fqn": "my-project.sales.orders_summary",
  "direction": "UPSTREAM",
  "source_fqn": "bigquery:my-project.raw.orders",
  "target_fqn": "bigquery:my-project.sales.orders_summary",
  "source_column": "order_total",
  "target_column": "revenue",
  "process_name": "projects/my-project/locations/us/processes/abc123",
  "process_kind": "BIGQUERY_JOB",
  "lineage_source": "LINEAGE_API",
  "confidence": "HIGH",
  "observed_at": "2024-06-01T10:30:00Z",
  "fetched_at": "2026-05-20T09:00:00Z"
}
```
