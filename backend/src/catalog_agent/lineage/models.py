"""Pydantic models for lineage edges and reports."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

LineageSource = Literal["LINEAGE_API", "JOBS_FALLBACK"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
Direction = Literal["UPSTREAM", "DOWNSTREAM"]
ProcessKind = Literal["BIGQUERY_JOB", "DATAFLOW_JOB", "JOBS_HISTORY"]


class LineageEdge(BaseModel):
    """One directed lineage edge, from one source to one target (either table or column level)."""

    project_id: str
    dataset_id: str
    asset: str
    asset_fqn: str

    direction: Direction
    source_fqn: str | None = None
    target_fqn: str | None = None
    source_column: str | None = None
    target_column: str | None = None

    process_name: str | None = None
    process_kind: ProcessKind | None = None

    lineage_source: LineageSource
    confidence: Confidence

    observed_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_bq_dict(self) -> dict[str, object]:
        """Serialise to a flat dict matching the lineage_registry schema."""
        return {
            "project_id": self.project_id,
            "dataset_id": self.dataset_id,
            "asset": self.asset,
            "asset_fqn": self.asset_fqn,
            "direction": self.direction,
            "source_fqn": self.source_fqn,
            "target_fqn": self.target_fqn,
            "source_column": self.source_column,
            "target_column": self.target_column,
            "process_name": self.process_name,
            "process_kind": self.process_kind,
            "lineage_source": self.lineage_source,
            "confidence": self.confidence,
            "observed_at": self.observed_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
        }


class LineageReport(BaseModel):
    """Aggregated result of fetching lineage for a full dataset."""

    project_id: str
    dataset_id: str
    edges: list[LineageEdge] = Field(default_factory=list)

    @property
    def high_count(self) -> int:
        return sum(1 for e in self.edges if e.confidence == "HIGH")

    @property
    def medium_count(self) -> int:
        return sum(1 for e in self.edges if e.confidence == "MEDIUM")

    @property
    def low_count(self) -> int:
        return sum(1 for e in self.edges if e.confidence == "LOW")

    def summary(self) -> str:
        return (
            f"{len(self.edges)} edges fetched "
            f"(HIGH: {self.high_count}, MEDIUM: {self.medium_count}, LOW: {self.low_count})"
        )
