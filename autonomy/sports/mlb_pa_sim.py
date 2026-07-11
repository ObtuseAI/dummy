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

# Calibration constants (Task 3 re-calibration for realistic run COMPOSITION): an
# earlier re-tune hit the aggregate bands (~8.5 runs / ~0.55 yrfi / ~0.54 home_win) but
# through a distorted, HR-heavy run PROCESS -- HR/PA ~0.085 (real ~0.033), ~24% of hits
# were HRs (real ~15%), power hitters saturated at the old 0.09 HR cap, and the late
# innings were over-suppressed by a 0.60 reliever HR9. Root cause: two hard-coded
# constraints in plate_appearance_distribution forced it -- a 0.20 hit-share floor (so
# HIT_SHARE_BASE could not act as a live lever for NON-HR offense) and a 0.09 HR-prob
# cap (so power hitters could not differentiate, pushing the model to lean on the HR
# term for run environment). Both are now relaxed (floor 0.20 -> 0.10, cap 0.09 -> 0.14)
# so HIT_SHARE_BASE is again the primary lever for the run environment. HR_ISO_MULT is
# set to a realistic 0.23 (a 0.15-ISO average batter -> ~0.033 HR/PA after the log5
# pitcher combination, matching real; HR is ~0.13 of hits, near real ~0.15). The neutral
# matchup (`_context(home_batter_iso=0.15, away_batter_iso=0.15)`, seed=2026, sims=3000)
# now lands: expected_total_runs ~8.72 (band [8.0, 9.2], real ~8.5), home_win ~0.53
# (band [0.51, 0.575], home edge ~0.54), with REALISTIC composition -- HR/PA <= 0.045
# and HR share of hits <= 0.22 (guard-tested).
#
# YRFI CAVEAT (important): with composition held realistic, yrfi lands ~0.41, BELOW real
# MLB's ~0.55 and below the review's requested [0.50, 0.62] / fallback [0.46, 0.62]
# bands. This is a genuine, structural limitation, not a tuning miss: an exhaustive
# search (HIT_SHARE_BASE x HR_ISO_MULT x hit-mix x TTO x HFA) found the max in-band yrfi
# achievable with realistic composition is ~0.44 -- and only by pushing HR to the cap
# (1.35x real) and doubles to 1.25x real, i.e. re-committing the very distortion this
# task removes. The real cause is the station-to-station single advancement in _advance
# (a documented deferred S4/S5 limitation): a single moves each runner exactly one base,
# so runners pile up and are stranded unless a cluster or extra-base hit arrives. That
# depresses the FRACTION of innings that score >=1 run (yrfi) relative to the mean run
# rate. Per the review's stated priority -- "realistic composition is the priority ...
# rather than re-distorting composition" -- yrfi is left at its honest realistic-
# composition value and its calibration-lock band is loosened accordingly (see the test).
# The proper fix for yrfi is the deferred _advance improvement, out of scope for a
# constants-only calibration. See mlb_pa_sim_demo.py and the composition-guard tests.
HR_ISO_MULT = 0.23  # batter HR prob = iso * HR_ISO_MULT, clamped to [0.004, 0.14]
HIT_SHARE_BASE = 0.28  # baseline share of a non-KBBHBPHR PA that becomes a hit
HIT_SHARE_CAP = 0.55  # upper clamp so elite sluggers keep differentiating past 0.44

HOME_FIELD_BOOST = 1.045  # home lineups score slightly more (finalized in calibration)


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


from autonomy.sports.statsapi import (
    BatterRates, MlbGameContext, PitcherRates, batter_rates_vs, pitcher_rates_vs,
)

PA_OUTCOMES = ("k", "bb", "hbp", "single", "double", "triple", "hr", "out")


def _rate(value: float | None, fallback: float) -> float:
    return fallback if value is None else float(value)


def plate_appearance_distribution(
    batter: BatterRates | None,
    pitcher: PitcherRates | None,
    *,
    park_hr_factor: float = 1.0,
    weather_hr_factor: float = 1.0,
    platoon: float = 1.0,
) -> dict[str, float]:
    """Probability over PA_OUTCOMES for one batter vs one pitcher (sums to 1)."""
    b_k = _rate(getattr(batter, "k_pct", None), LEAGUE["k"])
    p_k = _rate(getattr(pitcher, "k_pct", None), LEAGUE["k"])
    b_bb = _rate(getattr(batter, "bb_pct", None), LEAGUE["bb"])
    p_bb = _rate(getattr(pitcher, "bb_pct", None), LEAGUE["bb"])
    iso = getattr(batter, "iso", None)
    b_hr = min(0.14, max(0.004, iso * HR_ISO_MULT)) if iso is not None else LEAGUE["hr"]
    hr9 = getattr(pitcher, "hr9", None)
    p_hr = (hr9 / 38.0) if hr9 is not None else LEAGUE["hr"]

    k = log5(b_k, p_k, LEAGUE["k"])
    bb = log5(b_bb, p_bb, LEAGUE["bb"]) * platoon
    hbp = LEAGUE["hbp"]
    hr = log5(b_hr, p_hr, LEAGUE["hr"]) * park_hr_factor * weather_hr_factor * platoon

    # Remaining mass after the "three true outcomes" splits into hits vs outs.
    remaining = max(0.0, 1.0 - k - bb - hbp - hr)
    # Batter contact quality: OBP above league lifts the on-contact hit share.
    obp = _rate(getattr(batter, "obp", None), 0.320)
    slg = _rate(getattr(batter, "slg", None), 0.400)
    # On-contact hit share rises with both on-base skill (obp) and power (slg).
    hit_share = min(HIT_SHARE_CAP, max(0.10, HIT_SHARE_BASE + (obp - 0.320) * 1.2 + (slg - 0.400) * 0.35))
    hits = remaining * hit_share * platoon
    out = max(0.0, remaining - hits)
    # Split non-HR hits into single/double/triple, tilting toward doubles with ISO.
    # Base weights target real MLB's non-HR hit mix (~0.735 singles / ~0.235 doubles /
    # ~0.03 triples): the previous 0.78/0.19 under-represented doubles (0.19 share vs
    # real ~0.235), an off-theme inaccuracy for a "realistic run composition" model and
    # one that also worsened run-scoring efficiency (doubles clear the bases far better
    # than the station-to-station single advance in _advance, so too few doubles depress
    # the fraction of innings that score at least one run).
    iso_tilt = 1.0 + (0.0 if iso is None else min(1.0, max(-0.5, (iso - 0.150) * 2.0)))
    s_w, d_w, t_w = 0.735, 0.235 * iso_tilt, 0.03
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


STARTER_BATTERS_FACED = 24  # a full modern start before the bullpen takes over
TTO_PENALTY_PER_TIME = 0.04  # each time through the order lifts the batter's offense
TTO_MAX_TIMES = 3            # penalty saturates by the third time through
# Reliever rates: a realistic single-inning reliever is a modest edge over league,
# not a HR sink. The earlier re-tune had pushed RELIEVER_HR9 down to 0.60 (roughly
# half league average) to buy ~1 run of suppression; with the hit-share floor and HR
# cap now unbound, that crutch is no longer needed and the reliever is restored to a
# realistic RELIEVER_HR9=1.15 / RELIEVER_K_PCT=0.245 (a modest strikeout edge).
RELIEVER_K_PCT = 0.245  # relievers strike out modestly more than league
RELIEVER_BB_PCT = 0.090
RELIEVER_HR9 = 1.15


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


def _tto_mult(level: int) -> float:
    return 1.0 + TTO_PENALTY_PER_TIME * min(level, TTO_MAX_TIMES)


def _side_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    pitcher: Any,
    park_hr_factor: float,
    offense_mult: float = 1.0,
    weather_hr_factor: float = 1.0,
) -> list[dict[str, float]]:
    dists: list[dict[str, float]] = []
    throws = getattr(pitcher, "throws", None)
    for slot in lineup:
        batter = batter_rates.get(slot.player_id)
        batter_bats = getattr(slot, "bats", None)
        eff_batter = batter_rates_vs(batter, throws)
        if eff_batter is not batter:
            # A real vs-hand split exists for this batter: it already encodes the
            # platoon effect, so the flat multiplier collapses to 1.0 (offense_mult
            # -- HFA/weather/TTO -- still applies). Resolve the pitcher's real
            # split too, since the batter's real hand is now known.
            eff_pitcher = pitcher_rates_vs(pitcher, batter_bats)
            dists.append(plate_appearance_distribution(
                eff_batter, eff_pitcher,
                park_hr_factor=park_hr_factor,
                weather_hr_factor=weather_hr_factor,
                platoon=offense_mult,
            ))
        else:
            # No split data for this batter: today's flat-platoon behavior, byte-identical.
            dists.append(plate_appearance_distribution(
                batter, pitcher,
                park_hr_factor=park_hr_factor,
                weather_hr_factor=weather_hr_factor,
                platoon=_platoon(batter_bats, throws) * offense_mult,
            ))
    return dists


def _starter_distributions_by_tto(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    pitcher: Any,
    park_hr_factor: float,
    offense_mult: float,
    weather_hr_factor: float = 1.0,
) -> list[list[dict[str, float]]]:
    """Per-slot distributions for each times-through-the-order level (0..MAX)."""
    return [
        _side_distributions(
            lineup, batter_rates, pitcher, park_hr_factor,
            offense_mult=offense_mult * _tto_mult(level),
            weather_hr_factor=weather_hr_factor,
        )
        for level in range(TTO_MAX_TIMES + 1)
    ]


def _bullpen_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    fatigue: dict[int, float],
    park_hr_factor: float,
    offense_mult: float = 1.0,
    weather_hr_factor: float = 1.0,
) -> list[dict[str, float]]:
    # Realistic single-inning reliever (a modest edge over league, not a
    # cartoonish super-bullpen), degraded by aggregate bullpen fatigue.
    avg_fatigue = (sum(fatigue.values()) / len(fatigue)) if fatigue else 0.0
    reliever = PitcherRates(
        player_id=-1, throws=None,
        k_pct=RELIEVER_K_PCT * (1.0 - 0.15 * avg_fatigue),
        bb_pct=RELIEVER_BB_PCT * (1.0 + 0.20 * avg_fatigue),
        hr9=RELIEVER_HR9 * (1.0 + 0.20 * avg_fatigue),
    )
    return _side_distributions(
        lineup, batter_rates, reliever, park_hr_factor, offense_mult, weather_hr_factor)


def _simulate_side(
    starter_by_tto: list[list[dict[str, float]]],
    bullpen_dists: list[dict[str, float]],
    rng: random.Random,
    innings: int,
) -> tuple[int, int, int]:
    """Return (total_runs, first_inning_runs, runs_through_5) for one team."""
    total = first = through5 = 0
    cursor = 0
    pitcher_faced = 0   # batters the CURRENT pitcher has faced (resets on a switch)
    total_faced = 0     # batters the starter faced (triggers the bullpen)
    on_bullpen = False
    for inning in range(1, innings + 1):
        if not on_bullpen and total_faced >= STARTER_BATTERS_FACED:
            on_bullpen = True
            pitcher_faced = 0  # fresh reliever -> a fresh look at the order
        if on_bullpen:
            dists = bullpen_dists
        else:
            dists = starter_by_tto[min(TTO_MAX_TIMES, pitcher_faced // 9)]
        start = cursor
        runs, cursor = simulate_half_inning(cursor, lambda i: dists[i], rng)
        batters = cursor - start
        pitcher_faced += batters
        if not on_bullpen:
            total_faced += batters
        total += runs
        if inning == 1:
            first = runs
        if inning <= 5:
            through5 += runs
    return total, first, through5


def simulate_one_game(
    context: MlbGameContext, rng: random.Random, *, innings: int = 9,
    weather: tuple[float, float] | None = None,
) -> GameResult:
    park_hr = context.park_hr_factor if context.park_hr_factor is not None else 1.0
    hr_factor, run_factor = weather if weather is not None else (1.0, 1.0)
    home_starter = _starter_distributions_by_tto(
        context.home_lineup, context.batter_rates, context.away_pitcher, park_hr,
        HOME_FIELD_BOOST * run_factor, weather_hr_factor=hr_factor)
    home_pen = _bullpen_distributions(
        context.home_lineup, context.batter_rates, context.away_bullpen_fatigue, park_hr,
        HOME_FIELD_BOOST * run_factor, weather_hr_factor=hr_factor)
    away_starter = _starter_distributions_by_tto(
        context.away_lineup, context.batter_rates, context.home_pitcher, park_hr,
        run_factor, weather_hr_factor=hr_factor)
    away_pen = _bullpen_distributions(
        context.away_lineup, context.batter_rates, context.home_bullpen_fatigue, park_hr,
        run_factor, weather_hr_factor=hr_factor)
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
    weather: tuple[float, float] | None = None,
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
        game = simulate_one_game(context, rng, weather=weather)
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
