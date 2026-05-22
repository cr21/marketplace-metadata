"""Pydantic models for the data catalog registry."""

import json
from typing import Any

from pydantic import BaseModel


class ColumnRecord(BaseModel):
    """Represents one column in a BQ table/view, matching the REPEATED RECORD schema."""

    name: str
    data_type: str
    description: str = ""
    is_pii: bool = False


class CatalogRow(BaseModel):
    """One row in data_catalog_registry — one asset (table/view/routine) per row."""

    project_id: str
    dataset_id: str
    asset: str
    asset_type: str  # TABLE | VIEW | MATERIALIZED_VIEW | EXTERNAL | ROUTINE
    table_metadata: dict[str, Any]
    columns: list[ColumnRecord] = []

    def to_bq_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for the JSON rows parameter of merge_catalog_rows.

        table_metadata is serialized with sorted keys so the string is deterministic
        across runs — required for the MERGE idempotency check.
        """
        return {
            "project_id": self.project_id,
            "dataset_id": self.dataset_id,
            "asset": self.asset,
            "asset_type": self.asset_type,
            "table_metadata": json.dumps(self.table_metadata, sort_keys=True, default=str),
            "columns": [
                {
                    "name": col.name,
                    "data_type": col.data_type,
                    "description": col.description,
                    "is_pii": col.is_pii,
                }
                for col in self.columns
            ],
        }


class MergeResult(BaseModel):
    """Counts returned by merge_catalog_rows."""

    inserted: int
    updated: int
    unchanged: int
