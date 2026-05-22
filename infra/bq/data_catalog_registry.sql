-- DDL for data_catalog_registry
-- Reference only — this table already exists in BQ.
-- Do NOT run against the target project without a schema-changes.md entry.
--
-- Target: project-5c016d48-80d5-4534-b69.catalog_registry.data_catalog_registry
-- Primary key (logical): (project_id, dataset_id, asset)

CREATE TABLE IF NOT EXISTS `project-5c016d48-80d5-4534-b69.catalog_registry.data_catalog_registry`
(
  project_id     STRING    OPTIONS (description = 'GCP project that was crawled'),
  dataset_id     STRING    OPTIONS (description = 'BigQuery dataset that was crawled'),
  asset          STRING    OPTIONS (description = 'Table, view, or routine name'),
  asset_type     STRING    OPTIONS (description = 'TABLE | VIEW | MATERIALIZED_VIEW | EXTERNAL | ROUTINE'),
  table_metadata STRING    OPTIONS (description = 'JSON blob: description, labels, row_count, size_bytes, created, modified, clustering_fields, partitioning, routine_definition, pii_rationale'),
  columns        ARRAY<STRUCT<
    name         STRING    OPTIONS (description = 'Column name'),
    data_type    STRING    OPTIONS (description = 'BigQuery data type (full type string for STRUCT/ARRAY)'),
    description  STRING    OPTIONS (description = 'Column description from INFORMATION_SCHEMA or LLM-generated'),
    is_pii       BOOL      OPTIONS (description = 'True if column likely contains PII')
  >>             OPTIONS (description = 'REPEATED RECORD — empty for routines')
);
