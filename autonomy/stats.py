"""Shared normal-approximation confidence-interval helpers."""
from __future__ import annotations

import math
from typing import Any, Sequence


def mean_ci95(
    values: Sequence[float], *, collapse_single: bool = False
) -> dict[str, Any] | None:
    """Mean with a 95% normal CI.

    A single sample has no dispersion estimate: bounds are ``None`` unless
    ``collapse_single`` is set, in which case they collapse to the mean.
    """
    if not values:
        return None
    numbers = [float(value) for value in values]
    mean = sum(numbers) / len(numbers)
    if len(numbers) < 2:
        bound = round(mean, 6) if collapse_single else None
        return {
            "mean": round(mean, 6),
            "lower": bound,
            "upper": bound,
            "n": len(numbers),
            "method": "normal_mean_95",
        }
    variance = sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1)
    half = 1.96 * math.sqrt(variance / len(numbers))
    return {
        "mean": round(mean, 6),
        "lower": round(mean - half, 6),
        "upper": round(mean + half, 6),
        "n": len(numbers),
        "method": "normal_mean_95",
    }
