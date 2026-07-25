"""Allocation weight from a scope's demonstrated edge over the market.

The driver is CONTESTED BRIER ADVANTAGE: how much better the model's Brier
score is than the market's own price, on the same rows.  See
``autonomy/scope_analytics.py``, where ``brier_edge = market_brier -
model_brier_contested`` and a positive number means the model beat the line.

The LOWER 95% BOUND is used, not the point estimate -- the same quantity the
promotion gate already tests for ``> 0`` in ``autonomy/backtest.py``.  A scope
with twelve lucky rows must not size up on evidence its sample count cannot
support; the bound collapses toward the floor when n is small, which is exactly
the behaviour wanted.

The floor is never zero.  A scope that can never be allocated can never settle,
never accrue evidence, and never earn a higher weight -- zero is an absorbing
state.  Deciding whether a scope may trade at all belongs to the promotion and
tier gates; this module only sizes what those gates already passed.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from autonomy.allocation_config import AllocationConfig


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def weight_for_advantage(
    advantage: float | None, *, min_weight: float, target_advantage: float
) -> float:
    """Map a contested-Brier advantage onto ``[min_weight, 1.0]``.

    Unknown, non-positive, or unusable advantage all resolve to the floor.
    """
    value = _numeric(advantage)
    if value is None or value <= 0.0 or target_advantage <= 0.0:
        return min_weight
    fraction = min(1.0, value / target_advantage)
    return min_weight + (1.0 - min_weight) * fraction


def weights_for_scopes(
    scopes: Iterable[str],
    advantages: Mapping[str, Any],
    *,
    config: AllocationConfig,
) -> dict[str, float]:
    """Resolve a weight for every scope, defaulting unknowns to the floor."""
    return {
        scope: weight_for_advantage(
            advantages.get(scope),
            min_weight=config.min_weight,
            target_advantage=config.target_advantage,
        )
        for scope in scopes
    }


__all__ = ["weight_for_advantage", "weights_for_scopes"]
