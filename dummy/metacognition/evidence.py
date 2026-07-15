"""Verified held-out evidence gates for Phase 5 metacognitive claims."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from dummy.world_model.models import digest_json

from .state import MetacognitiveValidationError


def _probability(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise MetacognitiveValidationError(f"{name} must be in [0, 1]")
    return parsed


def _brier(probability: float, result_yes: bool) -> float:
    return (probability - float(result_yes)) ** 2


@dataclass(frozen=True, slots=True)
class MetacognitiveEvaluationCase:
    case_id: str
    event_cluster_id: str
    prediction_probability: float
    fixed_coverage_probability: float
    result_yes: bool
    abstained: bool
    confidence_score: float
    difficulty_score: float
    baseline_resource_cost: float
    resource_aware_cost: float
    resource_aware_probability: float
    settlement_verified: bool
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.event_cluster_id.strip():
            raise MetacognitiveValidationError("evaluation case identity is required")
        for field_name in (
            "prediction_probability",
            "fixed_coverage_probability",
            "confidence_score",
            "difficulty_score",
            "baseline_resource_cost",
            "resource_aware_cost",
            "resource_aware_probability",
        ):
            object.__setattr__(
                self,
                field_name,
                _probability(getattr(self, field_name), field_name),
            )
        if type(self.result_yes) is not bool or self.settlement_verified is not True:
            raise MetacognitiveValidationError(
                "metacognitive evaluation requires verified boolean settlement"
            )
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise MetacognitiveValidationError("evaluation evidence is required")
        if len(set(evidence)) != len(evidence):
            raise MetacognitiveValidationError("evaluation evidence is duplicated")
        object.__setattr__(self, "evidence_ids", evidence)

    @property
    def forecast_correct(self) -> bool:
        return (self.prediction_probability >= 0.5) is self.result_yes

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "event_cluster_id": self.event_cluster_id,
            "prediction_probability": self.prediction_probability,
            "fixed_coverage_probability": self.fixed_coverage_probability,
            "result_yes": self.result_yes,
            "abstained": self.abstained,
            "confidence_score": self.confidence_score,
            "difficulty_score": self.difficulty_score,
            "baseline_resource_cost": self.baseline_resource_cost,
            "resource_aware_cost": self.resource_aware_cost,
            "resource_aware_probability": self.resource_aware_probability,
            "settlement_verified": self.settlement_verified,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MetacognitiveEvaluationCase:
        return cls(
            case_id=str(data["case_id"]),
            event_cluster_id=str(data["event_cluster_id"]),
            prediction_probability=float(data["prediction_probability"]),
            fixed_coverage_probability=float(data["fixed_coverage_probability"]),
            result_yes=data["result_yes"],
            abstained=data.get("abstained") is True,
            confidence_score=float(data["confidence_score"]),
            difficulty_score=float(data["difficulty_score"]),
            baseline_resource_cost=float(data["baseline_resource_cost"]),
            resource_aware_cost=float(data["resource_aware_cost"]),
            resource_aware_probability=float(data["resource_aware_probability"]),
            settlement_verified=data.get("settlement_verified") is True,
            evidence_ids=tuple(data["evidence_ids"]),
        )


def _cases(
    cases: tuple[MetacognitiveEvaluationCase, ...],
) -> tuple[MetacognitiveEvaluationCase, ...]:
    ordered = tuple(sorted(cases, key=lambda item: item.case_id))
    ids = tuple(item.case_id for item in ordered)
    clusters = tuple(item.event_cluster_id for item in ordered)
    if len(set(ids)) != len(ids) or len(set(clusters)) != len(clusters):
        raise MetacognitiveValidationError(
            "metacognitive evidence requires unique cases and event clusters"
        )
    return ordered


def _report(body: dict[str, object]) -> dict[str, object]:
    body["report_id"] = digest_json(body)
    return body


def abstention_value_report(
    cases: tuple[MetacognitiveEvaluationCase, ...],
    *,
    minimum_cases: int = 100,
    abstention_cost: float = 0.25,
) -> dict[str, object]:
    ordered = _cases(cases)
    enough = len(ordered) >= minimum_cases
    coverage = (
        sum(not item.abstained for item in ordered) / len(ordered)
        if ordered
        else 0.0
    )
    coverage_valid = 0.20 <= coverage <= 0.90
    fixed_loss = (
        sum(
            _brier(item.fixed_coverage_probability, item.result_yes)
            for item in ordered
        )
        / len(ordered)
        if ordered
        else None
    )
    selective_loss = (
        sum(
            abstention_cost
            if item.abstained
            else _brier(item.prediction_probability, item.result_yes)
            for item in ordered
        )
        / len(ordered)
        if ordered
        else None
    )
    passes = bool(
        enough
        and coverage_valid
        and fixed_loss is not None
        and selective_loss is not None
        and selective_loss < fixed_loss
    )
    status = "PASS" if passes else "FAIL" if enough else "INSUFFICIENT_SETTLED_EVIDENCE"
    return _report(
        {
            "schema_version": 1,
            "report_kind": "metacognitive_abstention_value",
            "status": status,
            "case_count": len(ordered),
            "unique_event_cluster_count": len(ordered),
            "minimum_cases": minimum_cases,
            "coverage": round(coverage, 12),
            "coverage_gate": [0.20, 0.90],
            "coverage_valid": coverage_valid,
            "abstention_cost": abstention_cost,
            "fixed_coverage_mean_loss": round(fixed_loss, 12) if enough else None,
            "metacognitive_mean_loss": round(selective_loss, 12) if enough else None,
            "decision_loss_improvement": (
                round(fixed_loss - selective_loss, 12) if enough else None
            ),
            "settlement_verified_only": True,
            "claim_supported": passes,
            "limitations": (
                []
                if passes
                else ["abstention_value_not_proven_on_required_held_out_clusters"]
            ),
        }
    )


def resource_efficiency_report(
    cases: tuple[MetacognitiveEvaluationCase, ...],
    *,
    minimum_cases: int = 100,
    quality_tolerance: float = 0.002,
) -> dict[str, object]:
    ordered = _cases(cases)
    enough = len(ordered) >= minimum_cases
    if ordered:
        baseline_cost = sum(item.baseline_resource_cost for item in ordered) / len(ordered)
        aware_cost = sum(item.resource_aware_cost for item in ordered) / len(ordered)
        baseline_brier = sum(
            _brier(item.fixed_coverage_probability, item.result_yes) for item in ordered
        ) / len(ordered)
        aware_brier = sum(
            _brier(item.resource_aware_probability, item.result_yes) for item in ordered
        ) / len(ordered)
    else:
        baseline_cost = aware_cost = baseline_brier = aware_brier = None
    cost_reduction = (
        (baseline_cost - aware_cost) / baseline_cost
        if baseline_cost is not None and baseline_cost > 0.0
        else None
    )
    regression = aware_brier - baseline_brier if aware_brier is not None else None
    passes = bool(
        enough
        and cost_reduction is not None
        and cost_reduction > 0.0
        and regression is not None
        and regression <= quality_tolerance
    )
    status = "PASS" if passes else "FAIL" if enough else "INSUFFICIENT_SETTLED_EVIDENCE"
    return _report(
        {
            "schema_version": 1,
            "report_kind": "resource_efficiency_without_quality_regression",
            "status": status,
            "case_count": len(ordered),
            "unique_event_cluster_count": len(ordered),
            "minimum_cases": minimum_cases,
            "mean_baseline_cost": round(baseline_cost, 12) if enough else None,
            "mean_resource_aware_cost": round(aware_cost, 12) if enough else None,
            "cost_reduction_fraction": round(cost_reduction, 12) if enough else None,
            "baseline_mean_brier": round(baseline_brier, 12) if enough else None,
            "resource_aware_mean_brier": round(aware_brier, 12) if enough else None,
            "brier_regression": round(regression, 12) if enough else None,
            "quality_tolerance": quality_tolerance,
            "settlement_verified_only": True,
            "claim_supported": passes,
            "limitations": (
                []
                if passes
                else ["resource_efficiency_claim_not_proven_on_held_out_clusters"]
            ),
        }
    )


def confidence_calibration_report(
    cases: tuple[MetacognitiveEvaluationCase, ...],
    *,
    minimum_cases: int = 100,
) -> dict[str, object]:
    ordered = _cases(cases)
    enough = len(ordered) >= minimum_cases
    confidence_brier = (
        sum(
            (item.confidence_score - float(item.forecast_correct)) ** 2
            for item in ordered
        )
        / len(ordered)
        if ordered
        else None
    )
    difficulty_brier = (
        sum(
            (item.difficulty_score - float(not item.forecast_correct)) ** 2
            for item in ordered
        )
        / len(ordered)
        if ordered
        else None
    )
    status = "EVALUATED" if enough else "INSUFFICIENT_SETTLED_EVIDENCE"
    return _report(
        {
            "schema_version": 1,
            "report_kind": "metacognitive_calibration",
            "status": status,
            "case_count": len(ordered),
            "unique_event_cluster_count": len(ordered),
            "minimum_cases": minimum_cases,
            "confidence_brier": round(confidence_brier, 12) if enough else None,
            "difficulty_brier": round(difficulty_brier, 12) if enough else None,
            "settlement_verified_only": True,
            "calibration_verified": enough,
            "limitations": (
                []
                if enough
                else ["metacognitive_mappings_remain_uncalibrated_shadow_outputs"]
            ),
        }
    )
