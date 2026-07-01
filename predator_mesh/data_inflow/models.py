"""Data inflow domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class SourceCategory(str, Enum):
    """High-level category for a data source."""

    RSS = "rss"
    NEWS_API = "news_api"
    SOCIAL = "social"
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    FILE = "file"
    MOCK = "mock"
    UNKNOWN = "unknown"


class SourceStatus(str, Enum):
    """Lifecycle status of a source candidate."""

    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    PRUNED = "pruned"
    DEGRADED = "degraded"


class DataSourceCandidate(BaseModel):
    """A discovered or registered data source with scoring dimensions."""

    source_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    name: str
    category: SourceCategory = SourceCategory.UNKNOWN
    status: SourceStatus = SourceStatus.CANDIDATE
    adapter_type: str = "mock"
    reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_s: float = Field(default=float("inf"), ge=0.0)
    latency_ms: float = Field(default=float("inf"), ge=0.0)
    uniqueness: float = Field(default=0.0, ge=0.0, le=1.0)
    edge_contribution: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_payload: dict[str, Any] = Field(default_factory=dict)
    score: Optional[Any] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    promotion_reason: Optional[str] = None
    prune_reason: Optional[str] = None

    @field_validator("sample_payload", mode="before")
    @classmethod
    def _coerce_sample_payload(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {"value": str(value)}

    def bump_updated_at(self) -> None:
        """Touch the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def to_signal_input(self) -> dict[str, Any]:
        """Return a redacted, signal-safe view of this candidate."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "category": self.category.value,
            "adapter_type": self.adapter_type,
            "reliability": self.reliability,
            "freshness_s": self.freshness_s,
            "latency_ms": self.latency_ms,
            "uniqueness": self.uniqueness,
            "edge_contribution": self.edge_contribution,
        }
