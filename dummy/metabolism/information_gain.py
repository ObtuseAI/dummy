"""Explicitly uncalibrated information-gain proxy for stopping research."""

from __future__ import annotations

import math

from .models import InformationGainEstimate, MetabolismValidationError


def estimate_information_gain_proxy(
    probabilities: tuple[float, ...],
    *,
    source_independence: float,
    calibration_reliability: float,
) -> InformationGainEstimate:
    if not probabilities:
        raise MetabolismValidationError("information-gain proxy requires forecasts")
    if any(not 0.0 <= float(value) <= 1.0 for value in probabilities):
        raise MetabolismValidationError("forecast probability is outside [0, 1]")
    if not 0.0 <= source_independence <= 1.0:
        raise MetabolismValidationError("source independence must be in [0, 1]")
    if not 0.0 <= calibration_reliability <= 1.0:
        raise MetabolismValidationError("calibration reliability must be in [0, 1]")
    mean = sum(probabilities) / len(probabilities)
    variance = sum((value - mean) ** 2 for value in probabilities) / len(probabilities)
    disagreement = min(1.0, math.sqrt(variance) * 2.0)
    proxy = disagreement * source_independence * calibration_reliability
    return InformationGainEstimate(
        proxy_value=round(proxy, 12),
        disagreement_component=round(disagreement, 12),
        independence_component=round(source_independence, 12),
        calibration_component=round(calibration_reliability, 12),
    )
