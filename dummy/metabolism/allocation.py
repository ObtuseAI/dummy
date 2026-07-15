"""Bounded recommendation-only resource allocation."""

from __future__ import annotations

from .models import MarginalUtility, UtilityStatus


def allocation_recommendation(utility: MarginalUtility) -> dict[str, object]:
    if utility.status is UtilityStatus.UNRESOLVED_UNMEASURED_COST:
        action = "NARROW_SCOPE"
        reason = "critical_compute_cost_unmeasured"
    elif utility.utility is not None and utility.utility < 0.0:
        action = "TERMINATE"
        reason = "estimated_marginal_utility_negative"
    else:
        action = "CONTINUE"
        reason = "estimated_marginal_utility_nonnegative"
    return {
        "action": action,
        "reason": reason,
        "applied": False,
        "authority": "RECOMMEND_ONLY",
        "automatic_resource_expansion": False,
    }
