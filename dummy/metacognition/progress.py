"""Stopping recommendation from guard state and marginal utility."""

from __future__ import annotations

from dummy.metabolism import MarginalUtility, UtilityStatus
from dummy.shadows import ShadowReview

from .state import ControlAction, ControlRecommendation, MetaCalibrationEvidence


def recommend_stopping(
    *,
    utility: MarginalUtility,
    shadow_review: ShadowReview,
    calibration: MetaCalibrationEvidence,
) -> ControlRecommendation:
    if shadow_review.hard_veto:
        action = ControlAction.TERMINATE
        reasons = ("shadow_guard_hard_veto",)
        applied = True
    elif utility.status is UtilityStatus.UNRESOLVED_UNMEASURED_COST:
        action = ControlAction.NARROW_SCOPE
        reasons = ("critical_resource_cost_unmeasured",)
        applied = False
    elif utility.utility is not None and utility.utility < 0.0:
        action = ControlAction.TERMINATE
        reasons = ("estimated_marginal_research_utility_negative",)
        applied = calibration.verified
    else:
        action = ControlAction.CONTINUE
        reasons = ("estimated_marginal_research_utility_nonnegative",)
        applied = False
    return ControlRecommendation(
        action=action,
        reasons=reasons,
        calibrated=calibration.verified,
        applied=applied,
        expected_information_gain_proxy=utility.information_gain.proxy_value,
    )
