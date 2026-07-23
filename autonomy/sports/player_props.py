"""Player minutes / usage projection and prop over-under pricing (challenger).

Prices a player counting-stat prop (points, rebounds, assists, ...) from the
player's own recent game log: project minutes (recency-weighted), project a
per-minute rate for the stat, multiply for the expected count, and price
over/under with a dispersion that reflects both count noise and a lighter
minutes uncertainty. Pure and deterministic; the caller supplies the game log.

Fail-closed at the edges: too few games, zero projected minutes, or a
non-finite projection yields no price (the signal abstains).
"""
from __future__ import annotations

import math
from typing import Any

MIN_GAMES = 5
# Recency weights (most-recent first); older games inform, recent games lead.
RECENCY_HALF_LIFE_GAMES = 6.0
# A player who plays more variable minutes has a more uncertain count; this
# scales the extra variance contributed by minutes noise.
MINUTES_VARIANCE_WEIGHT = 0.6


def _recency_weights(n: int) -> list[float]:
    decay = math.log(2.0) / RECENCY_HALF_LIFE_GAMES
    return [math.exp(-decay * i) for i in range(n)]


def _weighted_mean(values: list[float], weights: list[float]) -> float | None:
    total_w = sum(weights)
    if total_w <= 0:
        return None
    return sum(v * w for v, w in zip(values, weights)) / total_w


def project_minutes(recent_minutes: list[float]) -> float | None:
    """Recency-weighted projected minutes from the recent game log."""
    minutes = [m for m in recent_minutes if isinstance(m, (int, float)) and m >= 0]
    if len(minutes) < MIN_GAMES:
        return None
    return _weighted_mean(minutes, _recency_weights(len(minutes)))


def project_stat(
    game_log: list[dict[str, Any]], stat: str,
) -> dict[str, Any] | None:
    """Project the expected count and its dispersion for ``stat``.

    ``game_log`` is most-recent-first; each entry needs ``minutes`` and the
    stat key. Returns mean + sigma for a normal over/under, or None.
    """
    rows = [
        r for r in game_log
        if isinstance(r.get("minutes"), (int, float)) and r["minutes"] > 0
        and isinstance(r.get(stat), (int, float))
    ]
    if len(rows) < MIN_GAMES:
        return None
    weights = _recency_weights(len(rows))
    minutes = [float(r["minutes"]) for r in rows]
    per_minute = [float(r[stat]) / float(r["minutes"]) for r in rows]
    proj_minutes = _weighted_mean(minutes, weights)
    proj_rate = _weighted_mean(per_minute, weights)
    if proj_minutes is None or proj_rate is None or proj_minutes <= 0:
        return None
    mean = proj_minutes * proj_rate
    if not math.isfinite(mean) or mean <= 0:
        return None

    # Count dispersion: the realized per-game counts' spread, floored at a
    # Poisson-like sqrt(mean) so a short quiet streak never claims zero noise.
    counts = [float(r[stat]) for r in rows]
    count_mean = _weighted_mean(counts, weights) or mean
    var = _weighted_mean([(c - count_mean) ** 2 for c in counts], weights) or 0.0
    minutes_mean = proj_minutes
    minutes_var = _weighted_mean([(m - minutes_mean) ** 2 for m in minutes], weights) or 0.0
    minutes_component = MINUTES_VARIANCE_WEIGHT * (proj_rate ** 2) * minutes_var
    sigma = math.sqrt(max(var + minutes_component, mean, 1e-6))
    return {
        "stat": stat,
        "projected_minutes": round(proj_minutes, 2),
        "per_minute_rate": round(proj_rate, 5),
        "mean": round(mean, 3),
        "sigma": round(sigma, 3),
        "games": len(rows),
    }


def prop_over_probability(mean: float, sigma: float, line: float) -> float | None:
    """P(stat > line) under a normal, with a half-point continuity correction.

    Kalshi player-stat lines settle strictly over/under an integer or half
    line; the 0.5 continuity correction makes the normal approximation to the
    discrete count honest at integer lines.
    """
    if sigma <= 0 or not math.isfinite(mean):
        return None
    threshold = line + 0.5 if float(line).is_integer() else line
    z = (mean - threshold) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
