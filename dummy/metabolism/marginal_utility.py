"""Conservative marginal research-utility accounting."""

from __future__ import annotations

from .models import (
    CostEstimate,
    InformationGainEstimate,
    MarginalUtility,
    UtilityStatus,
)


def calculate_marginal_utility(
    information_gain: InformationGainEstimate,
    costs: CostEstimate,
    *,
    expected_calibration_value: float,
    expected_decision_improvement: float,
) -> MarginalUtility:
    for name, value in (
        ("expected_calibration_value", expected_calibration_value),
        ("expected_decision_improvement", expected_decision_improvement),
    ):
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    if costs.normalized_cost is None:
        utility = None
        status = UtilityStatus.UNRESOLVED_UNMEASURED_COST
    else:
        utility = round(
            information_gain.proxy_value
            + expected_calibration_value
            + expected_decision_improvement
            - costs.normalized_cost,
            12,
        )
        status = UtilityStatus.ESTIMATED_UNCALIBRATED
    return MarginalUtility(
        information_gain=information_gain,
        expected_calibration_value=expected_calibration_value,
        expected_decision_improvement=expected_decision_improvement,
        costs=costs,
        utility=utility,
        status=status,
    )
