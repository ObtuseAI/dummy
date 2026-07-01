"""Dataclasses and enums for the proof-weighted aggression governor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class AggressionDecision(str, Enum):
    """Discrete aggression decisions produced by the proof-weighted governor.

    The governor prices risk and translates a continuous allocation score into
    one of these deterministic actions.
    """

    PASS = "pass"
    HOLD = "hold"
    REDUCE = "reduce"
    ATTACK = "attack"
    ESCALATE = "escalate"


@dataclass
class AggressionAllocation:
    """Risk-priced allocation decision for a mesh opportunity.

    The allocation is bounded to [0.0, 1.0] and paired with a discrete decision
    so downstream components can choose a concrete action without re-deriving
    the logic.
    """

    decision: AggressionDecision = AggressionDecision.PASS
    size_pct: float = 0.0
    confidence: float = 0.0
    proof_reference: str = field(default_factory=lambda: f"agg_{str(uuid4())[:12]}")
    reasoning: str = ""
    blocked_by: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.size_pct = float(max(0.0, min(1.0, self.size_pct)))
        self.confidence = float(max(0.0, min(1.0, self.confidence)))

    def to_manifest_entry(self) -> dict[str, Any]:
        """Return a redacted, deterministic manifest entry for reports."""
        return {
            "decision": self.decision.value,
            "size_pct": round(self.size_pct, 6),
            "confidence": round(self.confidence, 6),
            "proof_reference": self.proof_reference,
            "reasoning": self.reasoning,
            "blocked_by": self.blocked_by,
            "meta": self.meta,
        }
