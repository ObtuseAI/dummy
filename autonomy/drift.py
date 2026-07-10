"""Online degradation diagnostics for ordered forecast-loss streams.

This module is deliberately observational. It never changes a source weight,
an allocation, or an order. River's ADWIN identifies statistically unusual
level changes; Dummy labels a change as degradation only when a local
post-change window is materially worse than the preceding window.
"""
from __future__ import annotations

from typing import Any, Iterable


def adwin_drift_report(
    values: Iterable[float],
    *,
    timestamps: Iterable[str] | None = None,
    delta: float = 0.002,
    min_degradation: float = 0.01,
    comparison_window: int = 64,
) -> dict[str, Any]:
    """Return deterministic ADWIN diagnostics for a higher-is-worse metric."""
    series = [float(value) for value in values]
    times = list(timestamps or [])
    if times and len(times) != len(series):
        raise ValueError("timestamps must have the same length as values")
    base: dict[str, Any] = {
        "available": False,
        "method": "river.drift.ADWIN",
        "metric_direction": "higher_is_worse",
        "delta": delta,
        "min_degradation": min_degradation,
        "observations": len(series),
        "drift_detected": False,
        "negative_drift": False,
        "detections": [],
    }
    if not series:
        base["note"] = "no ordered observations"
        return base
    try:
        from river.drift import ADWIN
    except ImportError:
        base["note"] = "install the analytics extra to enable River ADWIN"
        return base

    detector = ADWIN(delta=delta)
    detections: list[dict[str, Any]] = []
    for index, value in enumerate(series):
        detector.update(value)
        if not detector.drift_detected:
            continue
        window = min(comparison_window, (index + 1) // 2)
        if window < 8:
            continue
        after = series[index - window + 1:index + 1]
        before = series[index - (2 * window) + 1:index - window + 1]
        before_mean = sum(before) / len(before)
        after_mean = sum(after) / len(after)
        degradation = after_mean - before_mean
        detections.append({
            "index": index,
            "at": times[index] if times else None,
            "comparison_window": window,
            "before_mean": round(before_mean, 6),
            "after_mean": round(after_mean, 6),
            "change": round(degradation, 6),
            "negative": degradation >= min_degradation,
        })

    tail_width = min(comparison_window, len(series))
    tail = series[-tail_width:]
    base.update({
        "available": True,
        "drift_detected": bool(detections),
        "negative_drift": any(item["negative"] for item in detections),
        "detections": detections,
        "latest_detection": detections[-1] if detections else None,
        "latest_window_mean": round(sum(tail) / len(tail), 6),
        "latest_window_n": len(tail),
    })
    return base
