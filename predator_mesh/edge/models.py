"""Edge intelligence domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from predator_mesh.signals.models import NormalizedSignal


class EdgeDecision(str, Enum):
    """Discrete decision produced by the edge intelligence engine.

    Aligned with the Dummy V9 specification: only the following values are
    valid edge decisions.
    """

    ATTACK_REHEARSAL = "attack_rehearsal"
    WATCH = "watch"
    REQUIRE_MORE_EVIDENCE = "require_more_evidence"
    REQUIRE_MINIMAX_REVIEW = "require_minimax_review"
    NO_TRADE = "no_trade"
    STARVE_SIGNAL = "starve_signal"
    QUARANTINE_SOURCE = "quarantine_source"


class MarketTerrainSnapshot(BaseModel):
    """Public, redacted snapshot of current market conditions."""

    volatility_regime: str = "neutral"  # e.g., low, neutral, elevated, extreme
    liquidity_state: str = "normal"  # e.g., thin, normal, deep
    trend_direction: str = "sideways"  # e.g., up, down, sideways
    event_risk: str = "none"  # e.g., none, low, medium, high
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EdgeScore(BaseModel):
    """Decomposed edge score for a candidate opportunity."""

    conviction: float = Field(default=0.0)
    risk_adjusted_return: float = Field(default=0.0)
    time_horizon: float = Field(default=0.0)
    anomaly_strength: float = Field(default=0.0)
    consensus_divergence: float = Field(default=0.0)
    composite: float = Field(default=0.0)

    @field_validator("conviction", "time_horizon", "anomaly_strength", "consensus_divergence", "composite", mode="before")
    @classmethod
    def _clamp_unit(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @field_validator("risk_adjusted_return", mode="before")
    @classmethod
    def _clamp_signed(cls, value: float) -> float:
        return max(-1.0, min(1.0, float(value)))


class EdgeCandidate(BaseModel):
    """A scored opportunity mined from normalized signals and terrain."""

    candidate_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    signals: list[NormalizedSignal] = Field(default_factory=list)
    terrain: MarketTerrainSnapshot = Field(default_factory=MarketTerrainSnapshot)
    score: EdgeScore = Field(default_factory=EdgeScore)
    decision: EdgeDecision = EdgeDecision.NO_TRADE
    rationale: str = ""
    proof_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_manifest_entry(self) -> dict[str, Any]:
        """Return a redacted manifest entry for reports and dashboards."""
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "composite_score": self.score.composite,
            "signal_count": len(self.signals),
            "rationale": self.rationale,
            "proof_refs": self.proof_refs,
            "terrain": {
                "volatility_regime": self.terrain.volatility_regime,
                "liquidity_state": self.terrain.liquidity_state,
                "trend_direction": self.terrain.trend_direction,
                "event_risk": self.terrain.event_risk,
            },
        }

    def to_decision_report(self) -> dict[str, Any]:
        """Return a decision-focused report fragment."""
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "score": self.score.model_dump(),
            "rationale": self.rationale,
            "timestamp": self.created_at.isoformat(),
        }
