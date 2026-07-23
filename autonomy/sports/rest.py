"""Rest / travel / schedule-density as a calibrated MEAN shift (challenger).

Dummy's original rest handling only widened uncertainty; it never moved the
point estimate. Rest-differential (especially back-to-backs in basketball and
hockey) is a documented, small, real edge on the mean. This module computes
the point-in-time rest state from the history lake and applies a per-league
coefficient to the home team's win probability -- but the coefficient is
walk-forward-tuned (see autonomy.sports.tuner), so it stays ~0 where the lake
does not prove rest predicts outcomes (e.g. weekly football) and the model
degrades to the old uncertainty-only behaviour. Fail-closed: missing rest data
yields no shift.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

# Absolute clamp on the rest mean shift so a coefficient never dominates the
# quantitative prior; rest is a nudge, not a thesis.
MAX_REST_LOGIT_SHIFT = 0.35
# Rest-day difference beyond this is capped (a 6-day layoff is not 6x a 1-day).
REST_DIFF_CAP_DAYS = 3.0


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed


def rest_days(store: Any, team: str, as_of: str, league: str) -> float | None:
    """Days between the team's most recent completed game and ``as_of``.

    Point-in-time: only games strictly before ``as_of`` are consulted. None
    when the team has no prior game in the lake (cold start -> no shift).
    """
    as_of_dt = _parse(as_of)
    if as_of_dt is None:
        return None
    try:
        recent = store.team_form(team, as_of, league=league, n=1)
    except Exception:  # noqa: BLE001
        return None
    if not recent:
        return None
    last = _parse(recent[0].get("start_time"))
    if last is None or last >= as_of_dt:
        return None
    return (as_of_dt - last).total_seconds() / 86400.0


def _capped_diff(home_rest: float, away_rest: float) -> float:
    diff = home_rest - away_rest
    return max(-REST_DIFF_CAP_DAYS, min(REST_DIFF_CAP_DAYS, diff))


def rest_logit_shift(
    home_rest: float | None, away_rest: float | None, coefficient: float,
) -> float:
    """Bounded logit shift favouring the better-rested side.

    Positive shift = home advantage from more rest. Returns 0.0 when either
    rest value is unknown or the coefficient is zero (the σ-only fallback).
    """
    if home_rest is None or away_rest is None or coefficient == 0.0:
        return 0.0
    raw = coefficient * _capped_diff(home_rest, away_rest)
    return max(-MAX_REST_LOGIT_SHIFT, min(MAX_REST_LOGIT_SHIFT, raw))


def apply_rest_shift(
    probability_home: float, shift: float,
) -> float:
    """Apply a logit-space shift to a home win probability, clamped."""
    p = min(0.999, max(0.001, float(probability_home)))
    logit = math.log(p / (1.0 - p)) + float(shift)
    shifted = 1.0 / (1.0 + math.exp(-logit))
    return min(0.98, max(0.02, shifted))


def rest_state(
    store: Any, home: str, away: str, as_of: str, league: str,
) -> dict[str, Any]:
    """Point-in-time rest features for a matchup (JSON-safe, for the ledger)."""
    home_rest = rest_days(store, home, as_of, league)
    away_rest = rest_days(store, away, as_of, league)
    return {
        "home_rest_days": None if home_rest is None else round(home_rest, 3),
        "away_rest_days": None if away_rest is None else round(away_rest, 3),
        "home_back_to_back": home_rest is not None and home_rest <= 1.25,
        "away_back_to_back": away_rest is not None and away_rest <= 1.25,
        "rest_diff_days": (
            None if home_rest is None or away_rest is None
            else round(home_rest - away_rest, 3)
        ),
    }
