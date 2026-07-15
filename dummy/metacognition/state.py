"""Immutable Phase 5 metacognitive state contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MetacognitiveValidationError(ValueError):
    """A metacognitive state makes an unsupported or malformed claim."""


def _bounded(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise MetacognitiveValidationError(f"{name} must be in [0, 1]")
    return parsed


class KnowledgeBoundary(str, Enum):
    KNOWN = "KNOWN"
    PARTIALLY_KNOWN = "PARTIALLY_KNOWN"
    UNKNOWN = "UNKNOWN"
    UNSTABLE = "UNSTABLE"
    UNOBSERVABLE = "UNOBSERVABLE"
    OUTSIDE_AUTHORITY = "OUTSIDE_AUTHORITY"


class ControlAction(str, Enum):
    CONTINUE = "CONTINUE"
    EXPAND_EVIDENCE = "EXPAND_EVIDENCE"
    ADD_CHALLENGER = "ADD_CHALLENGER"
    ADD_ADVERSARY = "ADD_ADVERSARY"
    RECHECK_DATA = "RECHECK_DATA"
    REPLAY_ANALOGUES = "REPLAY_ANALOGUES"
    NARROW_SCOPE = "NARROW_SCOPE"
    REDUCE_CONFIDENCE = "REDUCE_CONFIDENCE"
    ABSTAIN = "ABSTAIN"
    TERMINATE = "TERMINATE"
    QUARANTINE_SOURCE = "QUARANTINE_SOURCE"


class MetaCalibrationState(str, Enum):
    VERIFIED = "VERIFIED"
    UNCALIBRATED_SHADOW = "UNCALIBRATED_SHADOW"


@dataclass(frozen=True, slots=True)
class MetaCalibrationEvidence:
    calibration_identity: str
    sample_size: int
    brier: float | None
    ece: float | None
    verified: bool
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.calibration_identity.strip() or self.sample_size < 0:
            raise MetacognitiveValidationError("meta-calibration identity is invalid")
        for field_name in ("brier", "ece"):
            value = getattr(self, field_name)
            if value is not None:
                _bounded(value, field_name)
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if any(not item for item in evidence) or len(set(evidence)) != len(evidence):
            raise MetacognitiveValidationError("meta-calibration evidence is invalid")
        if self.verified and (
            self.sample_size <= 0
            or self.brier is None
            or self.ece is None
            or not evidence
        ):
            raise MetacognitiveValidationError(
                "verified meta-calibration requires settled metrics and evidence"
            )
        object.__setattr__(self, "evidence_ids", evidence)

    @property
    def state(self) -> MetaCalibrationState:
        return (
            MetaCalibrationState.VERIFIED
            if self.verified
            else MetaCalibrationState.UNCALIBRATED_SHADOW
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_identity": self.calibration_identity,
            "sample_size": self.sample_size,
            "brier": self.brier,
            "ece": self.ece,
            "verified": self.verified,
            "state": self.state.value,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceDecomposition:
    model: float
    evidence_completeness: float
    evidence_freshness: float
    data_reliability: float
    regime_familiarity: float
    historical_analogue_strength: float
    calibration_reliability: float
    market_prior_agreement: float
    source_independence: float
    causal_confidence: float
    forecast_stability: float
    settlement_sample_support: float

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(
                self,
                field_name,
                _bounded(getattr(self, field_name), field_name),
            )

    @property
    def final(self) -> float:
        return round(min(getattr(self, field) for field in self.__dataclass_fields__), 12)

    @property
    def limiting_components(self) -> tuple[str, ...]:
        return tuple(
            field
            for field in self.__dataclass_fields__
            if math.isclose(getattr(self, field), self.final, abs_tol=1e-12)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **{
                field_name: getattr(self, field_name)
                for field_name in self.__dataclass_fields__
            },
            "final": self.final,
            "aggregation": "minimum_critical_component",
            "limiting_components": list(self.limiting_components),
        }


@dataclass(frozen=True, slots=True)
class DifficultyEstimate:
    score: float
    band: str
    reasons: tuple[str, ...]
    calibration: MetaCalibrationEvidence

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", _bounded(self.score, "difficulty score"))
        if self.band not in {"LOW", "MEDIUM", "HIGH", "EXTREME"}:
            raise MetacognitiveValidationError("difficulty band is invalid")
        reasons = tuple(sorted(str(item).strip() for item in self.reasons))
        if not reasons or any(not item for item in reasons):
            raise MetacognitiveValidationError("difficulty reasons are required")
        object.__setattr__(self, "reasons", reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band,
            "reasons": list(self.reasons),
            "calibration": self.calibration.to_dict(),
            "may_control_forecast": self.calibration.verified,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeBoundaryAssessment:
    state: KnowledgeBoundary
    reasons: tuple[str, ...]
    known_unknowns: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reasons": list(self.reasons),
            "known_unknowns": list(self.known_unknowns),
        }


@dataclass(frozen=True, slots=True)
class ControlRecommendation:
    action: ControlAction
    reasons: tuple[str, ...]
    calibrated: bool
    applied: bool
    expected_information_gain_proxy: float | None = None

    def __post_init__(self) -> None:
        if self.applied and not self.calibrated and self.action not in {
            ControlAction.ABSTAIN,
            ControlAction.TERMINATE,
            ControlAction.QUARANTINE_SOURCE,
        }:
            raise MetacognitiveValidationError(
                "uncalibrated metacognition cannot expand or continue control"
            )
        reasons = tuple(sorted(str(item).strip() for item in self.reasons))
        if not reasons or any(not item for item in reasons):
            raise MetacognitiveValidationError("control reasons are required")
        if self.expected_information_gain_proxy is not None:
            _bounded(
                self.expected_information_gain_proxy,
                "expected_information_gain_proxy",
            )
        object.__setattr__(self, "reasons", reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "reasons": list(self.reasons),
            "calibrated": self.calibrated,
            "applied": self.applied,
            "expected_information_gain_proxy": self.expected_information_gain_proxy,
            "authority": "RECOMMEND_ONLY" if not self.applied else "SAFETY_CONTRACTION",
        }


@dataclass(frozen=True, slots=True)
class MetacognitiveState:
    difficulty: DifficultyEstimate
    confidence: ConfidenceDecomposition
    knowledge_boundary: KnowledgeBoundaryAssessment
    disagreement: dict[str, Any]
    strategy: ControlRecommendation
    abstention: ControlRecommendation
    stopping: ControlRecommendation
    resource_allocation: dict[str, Any]
    shadow_only: bool = True

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise MetacognitiveValidationError("Phase 5 metacognition must be shadow-only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "difficulty": self.difficulty.to_dict(),
            "confidence": self.confidence.to_dict(),
            "knowledge_boundary": self.knowledge_boundary.to_dict(),
            "disagreement": self.disagreement,
            "strategy": self.strategy.to_dict(),
            "abstention": self.abstention.to_dict(),
            "stopping": self.stopping.to_dict(),
            "resource_allocation": self.resource_allocation,
            "shadow_only": self.shadow_only,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }
