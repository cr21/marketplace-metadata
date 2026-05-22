-- DDL for catalog_registry.lineage_registry
-- Primary key: (project_id, dataset_id, asset, direction, source_fqn, target_fqn,
--               source_column, target_column, lineage_source)
-- NULL values are permitted in source_fqn/target_fqn/source_column/target_column
-- and participate in the composite key via IS NOT DISTINCT FROM in MERGE statements.
--
-- Run: bq mk --table <project>:catalog_registry.lineage_registry infra/bq/lineage_registry.sql
-- Or:  make bq-init-lineage PROJECT=<project>

CREATE TABLE IF NOT EXISTS `catalog_registry.lineage_registry` (
  project_id     STRING  NOT NULL OPTIONS(description="GCP project ID of the crawled asset"),
  dataset_id     STRING  NOT NULL OPTIONS(description="BigQuery dataset of the crawled asset"),
  asset          STRING  NOT NULL OPTIONS(description="Asset name (table, view, routine)"),
  asset_fqn      STRING  NOT NULL OPTIONS(description="Fully-qualified name: project.dataset.asset"),
  direction      STRING  NOT NULL OPTIONS(description="UPSTREAM or DOWNSTREAM relative to asset_fqn"),
  source_fqn     STRING           OPTIONS(description="FQN of the source side of the edge"),
  target_fqn     STRING           OPTIONS(description="FQN of the target side of the edge"),
  source_column  STRING           OPTIONS(description="Source column name; NULL for table-level edges"),
  target_column  STRING           OPTIONS(description="Target column name; NULL for table-level edges"),
  process_name   STRING           OPTIONS(description="Lineage API process resource name; NULL for JOBS_FALLBACK"),
  process_kind   STRING           OPTIONS(description="BIGQUERY_JOB | DATAFLOW_JOB | JOBS_HISTORY"),
  lineage_source STRING  NOT NULL OPTIONS(description="LINEAGE_API | JOBS_FALLBACK"),
  confidence     STRING  NOT NULL OPTIONS(description="HIGH | MEDIUM | LOW"),
  observed_at    TIMESTAMP NOT NULL OPTIONS(description="When the lineage event was observed (from API or job timestamp)"),
  fetched_at     TIMESTAMP NOT NULL OPTIONS(description="When this row was written by the fetcher")
);
