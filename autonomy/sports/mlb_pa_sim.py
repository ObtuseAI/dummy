"""Plate-appearance Monte Carlo simulator for MLB games (`mlb_pa_sim`).

Simulates a game one plate appearance at a time: each batter vs the current
pitcher, combined by the Bill James log5 odds ratio against league average,
platoon- and park-adjusted. One simulated game yields a winner, a run total,
a first-inning run flag, and a first-five-innings result; aggregating many
games yields coherent market probabilities. Pure, offline, deterministic.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

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

# Calibration constants (Task 6): tuned so a neutral matchup (average batters vs
# average pitchers, `_context(home_batter_iso=0.15, away_batter_iso=0.15)`) lands
# in real-MLB run-environment bands -- expected_total_runs in [8.0, 9.5] (real
# MLB ~8.5), yrfi in [0.48, 0.62] (real MLB ~0.55), home_win in [0.47, 0.58].
# LEAGUE itself needed no change (its k/bb/hbp/hr entries were already close to
# real 2020s rates); the run environment was too low because on-contact hit
# share and HR-from-ISO were set conservatively. See mlb_pa_sim_demo.py.
HR_ISO_MULT = 0.20  # batter HR prob = iso * HR_ISO_MULT, clamped to [0.004, 0.09]
HIT_SHARE_BASE = 0.40  # baseline share of a non-KBBHBPHR PA that becomes a hit
HIT_SHARE_CAP = 0.55  # upper clamp so elite sluggers keep differentiating past 0.44


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


from autonomy.sports.statsapi import BatterRates, MlbGameContext, PitcherRates

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
    b_hr = min(0.09, max(0.004, iso * HR_ISO_MULT)) if iso is not None else LEAGUE["hr"]
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
    slg = _rate(getattr(batter, "slg", None), 0.400)
    # On-contact hit share rises with both on-base skill (obp) and power (slg).
    hit_share = min(HIT_SHARE_CAP, max(0.20, HIT_SHARE_BASE + (obp - 0.320) * 1.2 + (slg - 0.400) * 0.35))
    hits = remaining * hit_share * platoon
    out = max(0.0, remaining - hits)
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


def sample_outcome(dist: dict[str, float], rng: random.Random) -> str:
    """Weighted pick over PA_OUTCOMES using a seeded RNG."""
    roll = rng.random()
    cumulative = 0.0
    for outcome in PA_OUTCOMES:
        cumulative += dist.get(outcome, 0.0)
        if roll <= cumulative:
            return outcome
    return "out"


def _advance(bases: list[bool], outcome: str) -> int:
    """Advance runners for a hit/walk; return runs scored. bases = [1B,2B,3B]."""
    runs = 0
    if outcome in ("bb", "hbp"):
        # Force only: fill first empty base, push forced runners.
        if not bases[0]:
            bases[0] = True
        elif not bases[1]:
            bases[1] = True
        elif not bases[2]:
            bases[2] = True
        else:
            runs += 1  # bases loaded -> forced run, all stay
        return runs
    advance = {"single": 1, "double": 2, "triple": 3, "hr": 4}[outcome]
    # Move existing runners.
    new_bases = [False, False, False]
    for base_index in (2, 1, 0):
        if bases[base_index]:
            dest = base_index + advance
            if dest >= 3:
                runs += 1
            else:
                new_bases[dest] = True
    # Place the batter.
    if advance >= 4:
        runs += 1
    else:
        new_bases[advance - 1] = True
    bases[:] = new_bases
    return runs


def simulate_half_inning(
    start_cursor: int,
    pa_fn: Any,
    rng: random.Random,
) -> tuple[int, int]:
    """Simulate one half-inning; return (runs, next batting-order cursor)."""
    outs = 0
    runs = 0
    bases = [False, False, False]
    cursor = start_cursor
    while outs < 3:
        dist = pa_fn(cursor % 9)
        outcome = sample_outcome(dist, rng)
        cursor += 1
        if outcome in ("k", "out"):
            outs += 1
        else:
            runs += _advance(bases, outcome)
    return runs, cursor


STARTER_BATTERS_FACED = 20  # ~4-5 innings before the bullpen takes over (Task 6 calibration)
BULLPEN_K_BOOST = 1.7  # fresh reliever strikes out more than LEAGUE["k"] alone implies
BULLPEN_BASE_HR9 = 0.20  # fresh reliever allows far fewer HR/9 than a tiring starter


@dataclass(frozen=True)
class GameResult:
    home_runs: int
    away_runs: int
    home_first_inning_runs: int
    away_first_inning_runs: int
    home_runs_through_5: int
    away_runs_through_5: int


def _platoon(batter_bats: str | None, pitcher_throws: str | None) -> float:
    """Modest platoon multiplier: opposite hands favor the batter."""
    if not batter_bats or not pitcher_throws or batter_bats == "S":
        return 1.0
    return 0.93 if batter_bats == pitcher_throws else 1.07


def _side_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    pitcher: Any,
    park_hr_factor: float,
) -> list[dict[str, float]]:
    dists: list[dict[str, float]] = []
    throws = getattr(pitcher, "throws", None)
    for slot in lineup:
        batter = batter_rates.get(slot.player_id)
        dists.append(plate_appearance_distribution(
            batter, pitcher,
            park_hr_factor=park_hr_factor,
            platoon=_platoon(getattr(slot, "bats", None), throws),
        ))
    return dists


def _bullpen_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    fatigue: dict[int, float],
    park_hr_factor: float,
) -> list[dict[str, float]]:
    # Fresh, high-leverage single-inning reliever (real bullpens run measurably
    # cooler than a tiring/pacing starter), degraded by aggregate bullpen fatigue.
    avg_fatigue = (sum(fatigue.values()) / len(fatigue)) if fatigue else 0.0
    reliever = PitcherRates(
        player_id=-1, throws=None,
        k_pct=LEAGUE["k"] * BULLPEN_K_BOOST * (1.0 - 0.15 * avg_fatigue),
        bb_pct=LEAGUE["bb"] * (1.0 + 0.20 * avg_fatigue),
        hr9=BULLPEN_BASE_HR9 * (1.0 + 0.20 * avg_fatigue),
    )
    return _side_distributions(lineup, batter_rates, reliever, park_hr_factor)


def _simulate_side(
    starter_dists: list[dict[str, float]],
    bullpen_dists: list[dict[str, float]],
    rng: random.Random,
    innings: int,
) -> tuple[int, int, int]:
    """Return (total_runs, first_inning_runs, runs_through_5) for one team."""
    total = first = through5 = 0
    cursor = 0
    faced = 0
    for inning in range(1, innings + 1):
        use_bullpen = faced >= STARTER_BATTERS_FACED
        dists = bullpen_dists if use_bullpen else starter_dists
        start = cursor
        runs, cursor = simulate_half_inning(cursor, lambda i: dists[i], rng)
        faced += cursor - start
        total += runs
        if inning == 1:
            first = runs
        if inning <= 5:
            through5 += runs
    return total, first, through5


def simulate_one_game(
    context: MlbGameContext, rng: random.Random, *, innings: int = 9,
) -> GameResult:
    park_hr = context.park_hr_factor if context.park_hr_factor is not None else 1.0
    home_starter = _side_distributions(
        context.home_lineup, context.batter_rates, context.away_pitcher, park_hr)
    home_pen = _bullpen_distributions(
        context.home_lineup, context.batter_rates, context.away_bullpen_fatigue, park_hr)
    away_starter = _side_distributions(
        context.away_lineup, context.batter_rates, context.home_pitcher, park_hr)
    away_pen = _bullpen_distributions(
        context.away_lineup, context.batter_rates, context.home_bullpen_fatigue, park_hr)
    h_total, h_first, h_five = _simulate_side(home_starter, home_pen, rng, innings)
    a_total, a_first, a_five = _simulate_side(away_starter, away_pen, rng, innings)
    return GameResult(
        home_runs=h_total, away_runs=a_total,
        home_first_inning_runs=h_first, away_first_inning_runs=a_first,
        home_runs_through_5=h_five, away_runs_through_5=a_five,
    )


def simulate_game_markets(
    context: MlbGameContext,
    *,
    seed: int = 20260711,
    sims: int = 5000,
    total_line: float = 8.5,
) -> dict[str, Any]:
    """Run N deterministic games; return coherent market probabilities."""
    runs = max(1, int(sims))
    rng = random.Random(seed)
    home_wins = 0.0
    total_over = 0
    yrfi = 0
    home_f5 = 0
    total_runs_sum = 0
    for _ in range(runs):
        game = simulate_one_game(context, rng)
        if game.home_runs > game.away_runs:
            home_wins += 1.0
        elif game.home_runs == game.away_runs:
            home_wins += 0.5
        combined = game.home_runs + game.away_runs
        total_runs_sum += combined
        if combined > total_line:
            total_over += 1
        if game.home_first_inning_runs + game.away_first_inning_runs >= 1:
            yrfi += 1
        if game.home_runs_through_5 > game.away_runs_through_5:
            home_f5 += 1
    return {
        "home_win": home_wins / runs,
        "total_over": total_over / runs,
        "total_line": total_line,
        "yrfi": yrfi / runs,
        "home_f5_lead": home_f5 / runs,
        "expected_total_runs": total_runs_sum / runs,
        "sims": runs,
    }
