"""Calibrated-or-shadow-only abstention recommendations."""

from __future__ import annotations

from dummy.shadows import ShadowReview
from dummy.synthesis import SynthesisResult

from .state import (
    ConfidenceDecomposition,
    ControlAction,
    ControlRecommendation,
    KnowledgeBoundary,
    KnowledgeBoundaryAssessment,
    MetaCalibrationEvidence,
)


def recommend_abstention(
    *,
    synthesis: SynthesisResult,
    confidence: ConfidenceDecomposition,
    knowledge: KnowledgeBoundaryAssessment,
    shadow_review: ShadowReview,
    calibration: MetaCalibrationEvidence,
) -> ControlRecommendation:
    reasons: list[str] = []
    if shadow_review.requires_abstention:
        reasons.append("shadow_guard_requires_abstention")
    if confidence.final < 0.45:
        reasons.append("weakest_confidence_component_below_floor")
    if synthesis.edge_after_costs <= 0.0:
        reasons.append("edge_not_positive_after_cost_proxy")
    prior = synthesis.market_prior_probability
    low, high = synthesis.uncertainty_interval
    if low <= prior <= high:
        reasons.append("uncertainty_interval_overlaps_market_prior")
    if knowledge.state in {
        KnowledgeBoundary.UNKNOWN,
        KnowledgeBoundary.UNSTABLE,
        KnowledgeBoundary.UNOBSERVABLE,
        KnowledgeBoundary.OUTSIDE_AUTHORITY,
    }:
        reasons.append(f"knowledge_boundary_{knowledge.state.value.lower()}")
    recommend = bool(reasons)
    return ControlRecommendation(
        action=ControlAction.ABSTAIN if recommend else ControlAction.CONTINUE,
        reasons=tuple(reasons or ("no_shadow_abstention_condition",)),
        calibrated=calibration.verified,
        applied=shadow_review.requires_abstention,
    )
