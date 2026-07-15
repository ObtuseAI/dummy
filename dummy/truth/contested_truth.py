"""Contested-market filtering keeps trivial market agreement out of edge claims."""

from __future__ import annotations

from typing import Iterable


def contested_rows(
    rows: Iterable[tuple[str, float, float, float]],
    *,
    minimum_distance: float = 0.03,
) -> tuple[tuple[str, float], ...]:
    """Return (cluster, candidate Brier gain vs market) for contested rows."""

    result = []
    for cluster, candidate, market, outcome in rows:
        if abs(candidate - market) < minimum_distance:
            continue
        candidate_brier = (candidate - outcome) ** 2
        market_brier = (market - outcome) ** 2
        result.append((cluster, market_brier - candidate_brier))
    return tuple(result)


__all__ = ["contested_rows"]
