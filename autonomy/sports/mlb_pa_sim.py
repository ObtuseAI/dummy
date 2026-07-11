"""Plate-appearance Monte Carlo simulator for MLB games (`mlb_pa_sim`).

Simulates a game one plate appearance at a time: each batter vs the current
pitcher, combined by the Bill James log5 odds ratio against league average,
platoon- and park-adjusted. One simulated game yields a winner, a run total,
a first-inning run flag, and a first-five-innings result; aggregating many
games yields coherent market probabilities. Pure, offline, deterministic.
"""
from __future__ import annotations

# Approximate MLB-wide per-plate-appearance outcome rates (2020s). These are the
# fallback for missing player rates and the denominator for the log5 combination.
LEAGUE: dict[str, float] = {
    "k": 0.225,
    "bb": 0.085,
    "hbp": 0.011,
    "hr": 0.033,
    "single": 0.140,
    "double": 0.045,
    "triple": 0.004,
    "out": 0.457,  # in-play outs; the eight fields sum to 1.0
}


def log5(batter: float, pitcher: float, league: float) -> float:
    """Bill James odds-ratio combination of a batter and pitcher rate.

    Returns the probability of the event given a batter with rate `batter`
    facing a pitcher with rate `pitcher`, normalized against `league` average.
    Neutral inputs (both == league) return league; result clamped to [0, 1].
    """
    if league <= 0.0 or league >= 1.0:
        return min(1.0, max(0.0, 0.5 * (batter + pitcher)))
    b = min(0.999, max(0.001, batter))
    p = min(0.999, max(0.001, pitcher))
    numerator = (b * p) / league
    denominator = numerator + ((1.0 - b) * (1.0 - p)) / (1.0 - league)
    if denominator <= 0.0:
        return min(1.0, max(0.0, 0.5 * (batter + pitcher)))
    return min(1.0, max(0.0, numerator / denominator))


from typing import Any

from autonomy.sports.statsapi import BatterRates, PitcherRates

PA_OUTCOMES = ("k", "bb", "hbp", "single", "double", "triple", "hr", "out")


def _rate(value: float | None, fallback: float) -> float:
    return fallback if value is None else float(value)


def plate_appearance_distribution(
    batter: BatterRates | None,
    pitcher: PitcherRates | None,
    *,
    park_hr_factor: float = 1.0,
    platoon: float = 1.0,
) -> dict[str, float]:
    """Probability over PA_OUTCOMES for one batter vs one pitcher (sums to 1)."""
    b_k = _rate(getattr(batter, "k_pct", None), LEAGUE["k"])
    p_k = _rate(getattr(pitcher, "k_pct", None), LEAGUE["k"])
    b_bb = _rate(getattr(batter, "bb_pct", None), LEAGUE["bb"])
    p_bb = _rate(getattr(pitcher, "bb_pct", None), LEAGUE["bb"])
    iso = getattr(batter, "iso", None)
    b_hr = min(0.09, max(0.004, iso * 0.13)) if iso is not None else LEAGUE["hr"]
    hr9 = getattr(pitcher, "hr9", None)
    p_hr = (hr9 / 38.0) if hr9 is not None else LEAGUE["hr"]

    k = log5(b_k, p_k, LEAGUE["k"])
    bb = log5(b_bb, p_bb, LEAGUE["bb"]) * platoon
    hbp = LEAGUE["hbp"]
    hr = log5(b_hr, p_hr, LEAGUE["hr"]) * park_hr_factor * platoon

    # Remaining mass after the "three true outcomes" splits into hits vs outs.
    remaining = max(0.0, 1.0 - k - bb - hbp - hr)
    # Batter contact quality: OBP above league lifts the on-contact hit share.
    obp = _rate(getattr(batter, "obp", None), 0.320)
    hit_share = min(0.42, max(0.20, 0.30 + (obp - 0.320) * 1.5))
    hits = remaining * hit_share
    out = remaining - hits
    # Split non-HR hits into single/double/triple, tilting toward doubles with ISO.
    iso_tilt = 1.0 + (0.0 if iso is None else min(1.0, max(-0.5, (iso - 0.150) * 2.0)))
    s_w, d_w, t_w = 0.78, 0.19 * iso_tilt, 0.03
    wsum = s_w + d_w + t_w
    single = hits * s_w / wsum
    double = hits * d_w / wsum
    triple = hits * t_w / wsum

    dist = {
        "k": k, "bb": bb, "hbp": hbp, "single": single,
        "double": double, "triple": triple, "hr": hr, "out": out,
    }
    total = sum(dist.values())
    if total <= 0.0:
        return {key: LEAGUE[key] for key in PA_OUTCOMES}
    return {key: value / total for key, value in dist.items()}
