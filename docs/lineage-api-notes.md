# Lineage API Notes

Reference notes on the Google Cloud Data Lineage API (part of Dataplex).

---

## 1. Region scoping

The Lineage API is **region-scoped**. The client must be pointed at the correct regional endpoint:

```
{location}-datalineage.googleapis.com
```

For example, for the `us` multi-region:
```
us-datalineage.googleapis.com
```

If you query the wrong region, the API returns an empty result, not an error. This is the most common silent failure. Always confirm the region with:
```bash
bq show --format=prettyjson <project>:<dataset> | grep location
```

The `LINEAGE_LOCATION` env var (default `us`) must match the dataset's region exactly.

---

## 2. Asset FQN format

The Lineage API identifies assets using a **fully-qualified name (FQN)** with a system prefix:

```
bigquery:{project_id}.{dataset_id}.{table_name}
```

Example:
```
bigquery:my-project-123.sales.orders
```

Use `make_asset_fqn(project_id, dataset_id, asset)` from `catalog_agent.lineage.client` — do not string-format in multiple places.

---

## 3. Two-level API model

The Lineage API has two related concepts:

### Links (SearchLinks)
A **link** represents a table-level lineage relationship: one source entity → one target entity, via some process.

- `SearchLinksRequest` takes either a `source` **or** a `target` (not both) as an `EntityReference`.
- To get both UPSTREAM and DOWNSTREAM, make two calls per asset.
- Each `Link` has: `name`, `source`, `target`, `start_time`, `end_time`.

### Processes and ProcessLinks (BatchSearchLinkProcesses)
A **process** represents the computation that created the lineage (e.g. a BigQuery job). It may have **OpenLineage facets** attached that carry column-level information.

- `BatchSearchLinkProcessesRequest` takes a list of link names and returns `ProcessLinks` objects.
- Each `ProcessLinks` has a `process` resource name and a `links` repeated field.
- Each link in `links` may have `column_lineage_facets` with `field_transform_facets` → `(input_fields, output_field)` pairs.

Column-level lineage is only available when:
1. The process that wrote the data supports OpenLineage (BigQuery jobs do for CTAS/INSERT SELECT).
2. The API has had time to index it (eventually consistent — see §4).

---

## 4. Eventual consistency

The Lineage API is **eventually consistent**. A query that runs right now may not appear in the API for several minutes (sometimes longer for cross-region propagation).

**Implications for testing:**
- Integration tests must use long-stable lineage relationships (tables written days or weeks ago), not freshly-run queries.
- If `SearchLinks` returns zero results for an asset you know has lineage, wait a few minutes and retry.

---

## 5. Permissions required

| Operation | Required IAM role |
|-----------|-------------------|
| `SearchLinks` | `roles/datacatalog.lineageViewer` or `roles/bigquery.dataViewer` (project-level) |
| `BatchSearchLinkProcesses` | Same as above |

If the service account lacks these roles, the API returns `PERMISSION_DENIED`. The client wrapper catches this and returns `[]` with a warning log.

---

## 6. Python client library

Package: `google-cloud-datacatalog-lineage`
Module: `google.cloud.datacatalog_lineage_v1`

Key classes:
- `LineageClient` — the main client
- `EntityReference(fully_qualified_name=...)` — wraps an FQN
- `SearchLinksRequest(parent=..., source=... | target=...)` — one-direction link search
- `BatchSearchLinkProcessesRequest(parent=..., links=[...])` — process + column details

Regional client construction:
```python
from google.cloud import datacatalog_lineage_v1
client = datacatalog_lineage_v1.LineageClient(
    client_options={"api_endpoint": "us-datalineage.googleapis.com"}
)
```

---

## 7. Known limitations

- **No "both directions" in a single call.** Two calls per asset (UPSTREAM + DOWNSTREAM).
- **Column lineage is best-effort.** Many asset types only have table-level edges.
- **Large datasets may paginate.** `search_links` is auto-paginated by the library; `batch_search_link_processes` should be called in reasonable batches.
- **Dataflow jobs** produce lineage too (`process_kind="DATAFLOW_JOB"`), but their FQNs differ from BigQuery tables — handle gracefully.
