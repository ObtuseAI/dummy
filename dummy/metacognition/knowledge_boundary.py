"""Explicit classification of what the organism can and cannot know."""

from __future__ import annotations

from dummy.shadows import ShadowReview

from .state import KnowledgeBoundary, KnowledgeBoundaryAssessment


def classify_knowledge_boundary(
    *,
    completeness: float,
    forecast_spread: float,
    regime_familiarity: float,
    shadow_review: ShadowReview,
) -> KnowledgeBoundaryAssessment:
    reasons: list[str] = []
    unknowns: list[str] = []
    if any(finding.guard == "authority" and finding.action.name != "OBSERVE" for finding in shadow_review.findings):
        state = KnowledgeBoundary.OUTSIDE_AUTHORITY
        reasons.append("authority_guard_detected_out_of_scope_behavior")
    elif shadow_review.hard_veto:
        state = KnowledgeBoundary.UNSTABLE
        reasons.append("shadow_guard_hard_veto")
    elif forecast_spread >= 0.35:
        state = KnowledgeBoundary.UNSTABLE
        reasons.append("forecast_dispersion_extreme")
    elif completeness < 0.35:
        state = KnowledgeBoundary.UNKNOWN
        reasons.append("world_state_mostly_missing")
    elif completeness < 0.85 or regime_familiarity < 0.5:
        state = KnowledgeBoundary.PARTIALLY_KNOWN
        reasons.append("world_or_regime_state_incomplete")
    else:
        state = KnowledgeBoundary.KNOWN
        reasons.append("world_state_and_regime_coverage_high")
    if completeness < 1.0:
        unknowns.append("missing_optional_world_state")
    if regime_familiarity < 1.0:
        unknowns.append("regime_transfer_behavior")
    unknowns.extend(("post_decision_fillability", "unobserved_future_shock"))
    return KnowledgeBoundaryAssessment(
        state=state,
        reasons=tuple(sorted(reasons)),
        known_unknowns=tuple(sorted(set(unknowns))),
    )
