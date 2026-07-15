"""Recommendation-only strategy selection from explicit knowledge state."""

from __future__ import annotations

from .state import (
    ControlAction,
    ControlRecommendation,
    KnowledgeBoundary,
    KnowledgeBoundaryAssessment,
    MetaCalibrationEvidence,
)


def recommend_strategy(
    knowledge: KnowledgeBoundaryAssessment,
    calibration: MetaCalibrationEvidence,
) -> ControlRecommendation:
    mapping = {
        KnowledgeBoundary.KNOWN: ControlAction.CONTINUE,
        KnowledgeBoundary.PARTIALLY_KNOWN: ControlAction.EXPAND_EVIDENCE,
        KnowledgeBoundary.UNKNOWN: ControlAction.RECHECK_DATA,
        KnowledgeBoundary.UNSTABLE: ControlAction.ADD_ADVERSARY,
        KnowledgeBoundary.UNOBSERVABLE: ControlAction.NARROW_SCOPE,
        KnowledgeBoundary.OUTSIDE_AUTHORITY: ControlAction.TERMINATE,
    }
    action = mapping[knowledge.state]
    return ControlRecommendation(
        action=action,
        reasons=(f"knowledge_boundary_{knowledge.state.value.lower()}",),
        calibrated=calibration.verified,
        applied=(
            action is ControlAction.TERMINATE
            and knowledge.state is KnowledgeBoundary.OUTSIDE_AUTHORITY
        ),
    )
