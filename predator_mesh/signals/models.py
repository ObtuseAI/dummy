"""Signal ontology models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class SignalType(str, Enum):
    """Taxonomy of normalized signals."""

    PRICE_MOVE = "price_move"
    VOLUME_SPIKE = "volume_spike"
    SENTIMENT_SHIFT = "sentiment_shift"
    VOLATILITY_REGIME = "volatility_regime"
    LIQUIDITY_STRESS = "liquidity_stress"
    CALENDAR_EVENT = "calendar_event"
    ANOMALY = "anomaly"
    UNKNOWN = "unknown"


class NormalizedSignal(BaseModel):
    """A source-agnostic, redacted signal suitable for downstream lanes."""

    signal_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    signal_type: SignalType = SignalType.UNKNOWN
    strength: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    freshness: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_id: str = ""
    source_category: str = ""
    proof_refs: list[str] = Field(default_factory=list)
    raw_payload_redacted: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""

    @field_validator("strength", mode="before")
    @classmethod
    def _clamp_strength(cls, value: float) -> float:
        return max(-1.0, min(1.0, float(value)))

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def is_actionable(self, strength_threshold: float = 0.2) -> bool:
        """Return True if the signal is strong and confident enough."""
        return abs(self.strength) >= strength_threshold and self.confidence >= 0.5
