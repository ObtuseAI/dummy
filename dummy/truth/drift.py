"""Simple explicit drift state for train-to-transfer evidence."""

from __future__ import annotations

from typing import Any


def drift_state(
    *,
    training_mean: float | None,
    transfer_mean: float | None,
    tolerance: float,
) -> dict[str, Any]:
    if training_mean is None or transfer_mean is None:
        return {
            "status": "UNOBSERVED",
            "difference": None,
            "within_tolerance": False,
        }
    difference = abs(float(training_mean) - float(transfer_mean))
    return {
        "status": "STABLE" if difference <= tolerance else "DRIFTED",
        "difference": round(difference, 12),
        "within_tolerance": difference <= tolerance,
    }


__all__ = ["drift_state"]
