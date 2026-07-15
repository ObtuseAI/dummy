"""Typed inputs and outputs for structured family-capped synthesis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SynthesisValidationError(ValueError):
    """Structured synthesis input or output violates a reviewed bound."""


def _bounded(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise SynthesisValidationError(f"{name} must be in [0, 1]")
    return parsed


class CalibrationState(str, Enum):
    FULLY_CALIBRATED = "FULLY_CALIBRATED"
    PARTIALLY_CALIBRATED = "PARTIALLY_CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"


@dataclass(frozen=True, slots=True)
class SynthesisSource:
    agent_id: str
    role: str
    family_id: str
    probability_yes: float
    uncertainty: float
    proposed_weight: float
    calibrated: bool
    stale: bool
    regime_relevance: float
    independence: float
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("agent_id", "role", "family_id"):
            if not getattr(self, field_name).strip():
                raise SynthesisValidationError(f"{field_name} must be non-empty")
        probability = _bounded(self.probability_yes, "probability_yes")
        uncertainty = _bounded(self.uncertainty, "uncertainty")
        if uncertainty > 0.5:
            raise SynthesisValidationError("forecast uncertainty cannot exceed 0.5")
        weight = _bounded(self.proposed_weight, "proposed_weight")
        relevance = _bounded(self.regime_relevance, "regime_relevance")
        independence = _bounded(self.independence, "independence")
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise SynthesisValidationError("synthesis source requires evidence")
        if len(set(evidence)) != len(evidence):
            raise SynthesisValidationError("synthesis source evidence is duplicated")
        object.__setattr__(self, "probability_yes", probability)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "proposed_weight", weight)
        object.__setattr__(self, "regime_relevance", relevance)
        object.__setattr__(self, "independence", independence)
        object.__setattr__(self, "evidence_ids", evidence)


@dataclass(frozen=True, slots=True)
class FamilyCapPolicy:
    market_prior_floor: float = 0.50
    non_market_family_cap: float = 0.35
    uncalibrated_advisory_cap: float = 0.15
    policy_version: str = "phase5-family-caps-v1"

    def __post_init__(self) -> None:
        floor = _bounded(self.market_prior_floor, "market_prior_floor")
        family = _bounded(self.non_market_family_cap, "non_market_family_cap")
        advisory = _bounded(
            self.uncalibrated_advisory_cap,
            "uncalibrated_advisory_cap",
        )
        if floor < 0.50 or family > 1.0 - floor or advisory > family:
            raise SynthesisValidationError("family-cap policy is incoherent")
        if not self.policy_version.strip():
            raise SynthesisValidationError("family-cap policy version is required")
        object.__setattr__(self, "market_prior_floor", floor)
        object.__setattr__(self, "non_market_family_cap", family)
        object.__setattr__(self, "uncalibrated_advisory_cap", advisory)


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    probability_yes: float
    uncertainty_interval: tuple[float, float]
    source_weights: tuple[tuple[str, float], ...]
    family_weights: tuple[tuple[str, float], ...]
    market_prior_probability: float
    market_prior_weight: float
    market_prior_floor: float
    edge_after_costs: float
    calibration_state: CalibrationState
    dominant_evidence: tuple[str, ...]
    counterevidence: tuple[str, ...]
    excluded_sources: tuple[tuple[str, str], ...]
    policy_version: str

    def __post_init__(self) -> None:
        probability = _bounded(self.probability_yes, "synthesized probability")
        low, high = self.uncertainty_interval
        low = _bounded(low, "uncertainty lower bound")
        high = _bounded(high, "uncertainty upper bound")
        if not low <= probability <= high:
            raise SynthesisValidationError("uncertainty interval excludes forecast")
        source_weights = tuple(sorted(self.source_weights))
        family_weights = tuple(sorted(self.family_weights))
        if (
            not source_weights
            or not family_weights
            or len({key for key, _ in source_weights}) != len(source_weights)
            or len({key for key, _ in family_weights}) != len(family_weights)
            or any(not key.strip() for key, _ in (*source_weights, *family_weights))
        ):
            raise SynthesisValidationError("synthesis weights require unique identities")
        if not math.isclose(sum(value for _, value in source_weights), 1.0, abs_tol=1e-9):
            raise SynthesisValidationError("source weights must sum to one")
        if not math.isclose(sum(value for _, value in family_weights), 1.0, abs_tol=1e-9):
            raise SynthesisValidationError("family weights must sum to one")
        if any(not 0.0 <= value <= 1.0 for _, value in (*source_weights, *family_weights)):
            raise SynthesisValidationError("synthesis weights must be bounded")
        prior_probability = _bounded(
            self.market_prior_probability,
            "market_prior_probability",
        )
        prior_weight = _bounded(self.market_prior_weight, "market_prior_weight")
        floor = _bounded(self.market_prior_floor, "market_prior_floor")
        if floor < 0.50 or prior_weight + 1e-12 < floor:
            raise SynthesisValidationError("market-prior weight is below its floor")
        if not math.isfinite(float(self.edge_after_costs)):
            raise SynthesisValidationError("edge_after_costs must be finite")
        if not isinstance(self.calibration_state, CalibrationState):
            raise SynthesisValidationError("calibration_state is invalid")
        if not self.policy_version.strip():
            raise SynthesisValidationError("synthesis policy version is required")
        object.__setattr__(self, "probability_yes", probability)
        object.__setattr__(self, "uncertainty_interval", (low, high))
        object.__setattr__(self, "source_weights", source_weights)
        object.__setattr__(self, "family_weights", family_weights)
        object.__setattr__(self, "market_prior_probability", prior_probability)
        object.__setattr__(self, "market_prior_weight", prior_weight)
        object.__setattr__(self, "market_prior_floor", floor)

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecast_probability": self.probability_yes,
            "uncertainty_interval": list(self.uncertainty_interval),
            "source_weights": dict(self.source_weights),
            "family_weights": dict(self.family_weights),
            "market_prior_probability": self.market_prior_probability,
            "market_prior_weight": self.market_prior_weight,
            "market_prior_floor": self.market_prior_floor,
            "edge_after_costs": self.edge_after_costs,
            "calibration_state": self.calibration_state.value,
            "dominant_evidence": list(self.dominant_evidence),
            "counterevidence": list(self.counterevidence),
            "excluded_sources": [
                {"agent_id": agent_id, "reason": reason}
                for agent_id, reason in self.excluded_sources
            ],
            "policy_version": self.policy_version,
        }
