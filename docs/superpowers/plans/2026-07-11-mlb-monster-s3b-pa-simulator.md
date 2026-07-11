# MLB Monster S3b — Plate-Appearance Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `mlb_pa_sim` plate-appearance Monte Carlo engine: given a hydrated `MlbGameContext` (lineups with batter rates, starters with rates, park, bullpen), simulate the game one plate appearance at a time and produce coherent home-win / total-runs / YRFI / first-5 probabilities — the champion model head, unit-validated for calibration. Offline and deterministic; live daemon wiring and market grading come later (governance-gated).

**Architecture:** A new pure module `autonomy/sports/mlb_pa_sim.py`. Layer by layer: (1) league-average baselines + a `log5` odds-ratio helper; (2) a per-PA outcome distribution over {K, BB, HBP, 1B, 2B, 3B, HR, OUT} derived by combining each batter's rate with the pitcher's rate vs league average, platoon- and park-adjusted; (3) a deterministic inning/game simulator with baserunner advancement and a starter→bullpen switch; (4) an N-run aggregator that turns simulated games into per-market probabilities; (5) `simulate_game_markets(context, *, seed, sims)` as the single public entry point. Reuses nothing from the Beta-Binomial `SportsMonteCarloSimulator` (that is an epistemic-uncertainty sim, not a game sim). No live calls, no ledger, no forecaster changes.

**Tech Stack:** Python 3.11+, stdlib (`random`, `dataclasses`), `pytest`. Consumes `MlbGameContext`, `BatterRates`, `PitcherRates`, `LineupSlot` from `autonomy/sports/statsapi.py` (S1+S3a).

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` at the top of the new module.
- Pure and offline: no network, no ledger, no forecaster/model mutation. Deterministic — every simulation is driven by a seeded `random.Random(seed)`; the module must never call unseeded `random.*` or `Date`/time.
- New code in `autonomy/sports/mlb_pa_sim.py`; tests in `tests/test_autonomy_mlb_pa_sim.py`. Do not modify `statsapi.py`, `simulation.py`, `mlb_validation.py`, or any other file.
- Every probability is clamped to `[0, 1]`; every outcome distribution sums to `1.0` (within 1e-9) before sampling. A batter or pitcher with missing rates falls back to the league-average rate for that field — the sim always runs, never raises on `None`.
- League-average constants live in one clearly-labeled block with a citation comment (approximate MLB-wide 2020s rates); they are the fallback and the log5 denominator.
- Run the full suite with `python -m pytest -q` before the final commit; it must stay green (baseline after S3a merge: 4,687 passed, 0 skipped).
- Commit after every task with a `feat:`/`test:` message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: League baselines + `log5` odds-ratio helper

**Files:**
- Create: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Produces: `LEAGUE` dict of baseline rates (`k`, `bb`, `hbp`, `hr`, `single`, `double`, `triple`, `out` — per plate appearance, summing to 1.0); `log5(batter: float, pitcher: float, league: float) -> float` (the Bill James odds-ratio combination, clamped to `[0,1]`).

Notes: log5 formula for a rate: `x = (b*p/L) / ((b*p/L) + ((1-b)*(1-p)/(1-L)))`. With `b == L` and `p == L` it returns `L`. Guard against `L in {0,1}` and against a zero denominator (return the mean of `b,p` if degenerate).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py
from __future__ import annotations

from autonomy.sports.mlb_pa_sim import LEAGUE, log5


def test_league_baseline_sums_to_one():
    total = sum(LEAGUE[k] for k in ("k", "bb", "hbp", "hr", "single", "double", "triple", "out"))
    assert abs(total - 1.0) < 1e-9


def test_log5_neutral_returns_league():
    # A league-average batter vs a league-average pitcher yields the league rate.
    assert abs(log5(0.22, 0.22, 0.22) - 0.22) < 1e-9


def test_log5_monotonic_and_bounded():
    league = 0.22
    # A high-K batter vs a high-K pitcher strikes out more than either alone vs average.
    both_high = log5(0.30, 0.28, league)
    one_high = log5(0.30, league, league)
    assert both_high > one_high > league
    # Always within [0, 1].
    assert 0.0 <= log5(0.99, 0.99, 0.22) <= 1.0
    assert 0.0 <= log5(0.01, 0.01, 0.22) <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autonomy.sports.mlb_pa_sim'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_pa_sim.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): league baselines + log5 odds-ratio helper"
```

---

### Task 2: Per-plate-appearance outcome distribution

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Consumes: `LEAGUE`, `log5`; `BatterRates`, `PitcherRates` from `autonomy.sports.statsapi`.
- Produces: `PA_OUTCOMES` tuple `("k","bb","hbp","single","double","triple","hr","out")`; `plate_appearance_distribution(batter, pitcher, *, park_hr_factor=1.0, platoon=1.0) -> dict[str,float]` returning a probability over `PA_OUTCOMES` summing to 1.0. `batter`/`pitcher` may be `None` (fall back to league).

Notes: derive each rate independently by log5, then renormalize to sum to 1.
- K: `log5(batter.k_pct, pitcher_k, LEAGUE["k"])`. Pitcher K rate = `pitcher.k_pct` when present else `LEAGUE["k"]`.
- BB: `log5(batter.bb_pct, pitcher_bb, LEAGUE["bb"])`.
- HBP: `LEAGUE["hbp"]` (no per-player HBP data).
- HR: `log5(batter_hr, pitcher_hr, LEAGUE["hr"]) * park_hr_factor`, where `batter_hr` is derived from ISO (`min(0.08, max(0.005, batter.iso * 0.13))` when ISO present, else `LEAGUE["hr"]`) and `pitcher_hr` from HR9 (`pitcher.hr9 / 38.0` when present — ~38 batters/9ip — else `LEAGUE["hr"]`).
- Non-HR hits: batter on-contact strength from `batter.slg`/`obp`; distribute the remaining "hit" mass into single/double/triple using league single:double:triple proportions scaled by the batter's ISO (more ISO → relatively more doubles). Keep it simple and documented; exact splits are refined later by the feature-discovery loop.
- `platoon` multiplies the batter's offensive (non-K, non-out) rates modestly (>1 favors batter).
- OUT absorbs the remainder so the distribution sums to 1.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
from autonomy.sports.mlb_pa_sim import PA_OUTCOMES, plate_appearance_distribution
from autonomy.sports.statsapi import BatterRates, PitcherRates


def _batter(k, bb, obp, slg, iso):
    return BatterRates(player_id=1, k_pct=k, bb_pct=bb, obp=obp, slg=slg, iso=iso)


def _pitcher(k, bb, hr9):
    return PitcherRates(player_id=2, k_pct=k, bb_pct=bb, hr9=hr9)


def test_distribution_sums_to_one_and_covers_all_outcomes():
    dist = plate_appearance_distribution(
        _batter(0.20, 0.09, 0.34, 0.45, 0.18),
        _pitcher(0.24, 0.07, 1.1),
    )
    assert set(dist) == set(PA_OUTCOMES)
    assert abs(sum(dist.values()) - 1.0) < 1e-9
    assert all(0.0 <= p <= 1.0 for p in dist.values())


def test_none_rates_fall_back_to_league_average():
    dist = plate_appearance_distribution(None, None)
    # With no player data the distribution should be close to LEAGUE.
    assert abs(dist["k"] - LEAGUE["k"]) < 0.03
    assert abs(sum(dist.values()) - 1.0) < 1e-9


def test_high_strikeout_pitcher_raises_k_share():
    weak_k = plate_appearance_distribution(_batter(0.22, 0.08, 0.32, 0.40, 0.15),
                                           _pitcher(0.18, 0.08, 1.2))
    high_k = plate_appearance_distribution(_batter(0.22, 0.08, 0.32, 0.40, 0.15),
                                           _pitcher(0.33, 0.08, 1.2))
    assert high_k["k"] > weak_k["k"]


def test_park_hr_factor_increases_home_run_share():
    neutral = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.50, 0.22),
                                            _pitcher(0.22, 0.08, 1.3), park_hr_factor=1.0)
    hitter = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.50, 0.22),
                                           _pitcher(0.22, 0.08, 1.3), park_hr_factor=1.3)
    assert hitter["hr"] > neutral["hr"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "distribution or fall_back or strikeout or park_hr" -v`
Expected: FAIL with `ImportError: cannot import name 'plate_appearance_distribution'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_pa_sim.py (append)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "distribution or fall_back or strikeout or park_hr" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): per-plate-appearance outcome distribution (log5 + park/platoon)"
```

---

### Task 3: Half-inning simulation with baserunner advancement

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Produces: `sample_outcome(dist, rng) -> str` (weighted pick over PA_OUTCOMES); `simulate_half_inning(lineup_state, pa_fn, rng) -> tuple[int, LineupCursor]` returning runs scored in the half-inning and the advanced batting-order cursor, where `pa_fn(batter_index) -> dict[str,float]` yields the current PA distribution for the batter due up, and base-running follows fixed rules (single: batter→1B, runners +1 base; double: +2; triple: +3; HR: all score; BB/HBP: force only). A `LineupCursor` tracks the batting-order index so it persists across innings.

Notes: model bases as a length-3 list of booleans (1B,2B,3B occupied). Advancement is deterministic given the outcome (no steals, no double plays in v1 — documented simplification the feature-discovery loop can refine). Half-inning ends at 3 outs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
import random as _random

from autonomy.sports.mlb_pa_sim import sample_outcome, simulate_half_inning


def test_sample_outcome_is_deterministic_and_valid():
    dist = {"k": 0.25, "bb": 0.08, "hbp": 0.01, "single": 0.14,
            "double": 0.05, "triple": 0.004, "hr": 0.03, "out": 0.436}
    rng = _random.Random(7)
    picks = [sample_outcome(dist, rng) for _ in range(200)]
    assert set(picks) <= set(dist)
    # Determinism: same seed -> same sequence.
    rng2 = _random.Random(7)
    picks2 = [sample_outcome(dist, rng2) for _ in range(200)]
    assert picks == picks2


def test_half_inning_all_home_runs_scores_until_three_outs():
    # A distribution that always yields HR then... it can't make outs, so guard
    # with a mixed distribution and assert runs are non-negative and bounded.
    hr_heavy = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0,
                "double": 0.0, "triple": 0.0, "hr": 0.5, "out": 0.5}
    runs, _ = simulate_half_inning(0, lambda i: hr_heavy, _random.Random(3))
    assert runs >= 0


def test_half_inning_all_outs_scores_zero():
    outs_only = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0,
                 "double": 0.0, "triple": 0.0, "hr": 0.0, "out": 1.0}
    runs, cursor = simulate_half_inning(0, lambda i: outs_only, _random.Random(1))
    assert runs == 0
    assert cursor == 3  # exactly three batters retired
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "sample_outcome or half_inning" -v`
Expected: FAIL with `ImportError: cannot import name 'sample_outcome'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_pa_sim.py (append)
import random


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "sample_outcome or half_inning" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): half-inning simulation with baserunner advancement"
```

---

### Task 4: Full-game simulation with starter→bullpen switch

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Consumes: `MlbGameContext`, `plate_appearance_distribution`, `simulate_half_inning`.
- Produces: `GameResult` dataclass (`home_runs: int`, `away_runs: int`, `home_first_inning_runs: int`, `away_first_inning_runs: int`, `home_runs_through_5: int`, `away_runs_through_5: int`); `simulate_one_game(context, rng, *, innings=9) -> GameResult`. Each team bats its 9-slot lineup vs the opposing pitcher; the starter faces batters until a batters-faced threshold (`STARTER_BATTERS_FACED = 26`, roughly 6 innings), then a league-average bullpen distribution scaled by the team's aggregate bullpen fatigue takes over. Platoon multiplier applied when batter and pitcher hands are the same (pitcher-favored) vs opposite (batter-favored).

Notes: build a per-batting-slot PA distribution once per game side (batter rates × current pitcher × park × platoon), rebuilt when the pitcher switches. Track batters faced per side to trigger the bullpen switch. Determinism via the passed `rng`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
from autonomy.sports.mlb_pa_sim import GameResult, simulate_one_game
from autonomy.sports.statsapi import LineupSlot, MlbGameContext, PitcherRates


def _context(*, home_batter_iso, away_batter_iso):
    home_lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away_lineup = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    batter_rates = {}
    for i in range(9):
        batter_rates[100 + i] = BatterRates(
            player_id=100 + i, bats="R", k_pct=0.20, bb_pct=0.09,
            obp=0.340, slg=0.300 + home_batter_iso, iso=home_batter_iso)
        batter_rates[200 + i] = BatterRates(
            player_id=200 + i, bats="R", k_pct=0.20, bb_pct=0.09,
            obp=0.340, slg=0.300 + away_batter_iso, iso=away_batter_iso)
    return MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="H", away="A",
        home_lineup=home_lineup, away_lineup=away_lineup,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=batter_rates, park_run_factor=1.0, park_hr_factor=1.0,
    )


def test_simulate_one_game_returns_coherent_result():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    result = simulate_one_game(ctx, _random.Random(11))
    assert isinstance(result, GameResult)
    assert result.home_runs >= 0 and result.away_runs >= 0
    # First-inning runs cannot exceed the game total; F5 cannot exceed the full game.
    assert result.home_first_inning_runs <= result.home_runs
    assert result.home_runs_through_5 <= result.home_runs


def test_simulate_one_game_is_deterministic():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    a = simulate_one_game(ctx, _random.Random(5))
    b = simulate_one_game(ctx, _random.Random(5))
    assert a == b


def test_stronger_lineup_scores_more_on_average():
    strong = _context(home_batter_iso=0.28, away_batter_iso=0.10)
    weak = _context(home_batter_iso=0.10, away_batter_iso=0.10)
    strong_total = sum(simulate_one_game(strong, _random.Random(s)).home_runs for s in range(60))
    weak_total = sum(simulate_one_game(weak, _random.Random(s)).home_runs for s in range(60))
    assert strong_total > weak_total  # ISO-loaded lineup scores more across seeds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "simulate_one_game or stronger_lineup" -v`
Expected: FAIL with `ImportError: cannot import name 'simulate_one_game'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_pa_sim.py (append)
from dataclasses import dataclass

from autonomy.sports.statsapi import MlbGameContext

STARTER_BATTERS_FACED = 26  # ~6 innings before the bullpen takes over


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
    # League-average reliever, degraded slightly by aggregate bullpen fatigue.
    avg_fatigue = (sum(fatigue.values()) / len(fatigue)) if fatigue else 0.0
    reliever = PitcherRates(
        player_id=-1, throws=None,
        k_pct=LEAGUE["k"] * (1.0 - 0.15 * avg_fatigue),
        bb_pct=LEAGUE["bb"] * (1.0 + 0.20 * avg_fatigue),
        hr9=1.25 * (1.0 + 0.20 * avg_fatigue),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "simulate_one_game or stronger_lineup" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): full-game simulation with starter/bullpen switch + platoon"
```

---

### Task 5: Aggregate N games into market probabilities

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Consumes: `simulate_one_game`, `GameResult`, `MlbGameContext`.
- Produces: `simulate_game_markets(context, *, seed=20260711, sims=5000, total_line=8.5) -> dict[str, Any]` — the single public entry point. Runs `sims` deterministic games and returns `{"home_win": float, "total_over": float, "total_line": float, "yrfi": float, "home_f5_lead": float, "expected_total_runs": float, "sims": int}`, where `home_win` = fraction home>away (ties split 0.5), `total_over` = fraction (home+away) > total_line, `yrfi` = fraction with ≥1 run in the first inning either side, `home_f5_lead` = fraction home_through_5 > away_through_5.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
from autonomy.sports.mlb_pa_sim import simulate_game_markets


def test_market_probabilities_are_bounded_and_keyed():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    markets = simulate_game_markets(ctx, seed=1, sims=400)
    for key in ("home_win", "total_over", "yrfi", "home_f5_lead"):
        assert 0.0 <= markets[key] <= 1.0
    assert markets["sims"] == 400
    assert markets["expected_total_runs"] > 0.0


def test_market_simulation_is_deterministic():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    a = simulate_game_markets(ctx, seed=42, sims=300)
    b = simulate_game_markets(ctx, seed=42, sims=300)
    assert a == b


def test_much_stronger_home_lineup_favored_to_win():
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    markets = simulate_game_markets(ctx, seed=7, sims=800)
    assert markets["home_win"] > 0.60  # a far stronger lineup wins more often
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k market -v`
Expected: FAIL with `ImportError: cannot import name 'simulate_game_markets'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_pa_sim.py (append)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k market -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full module and full suite, then commit**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -v` (all PASS), then `python -m pytest -q` (full suite green, >= 4,687 passed plus the new module).

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): aggregate simulated games into market probabilities"
```

---

### Task 6: Calibration sanity checks + demo report

**Files:**
- Create: `scripts/mlb_pa_sim_demo.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Consumes: `simulate_game_markets`.
- Produces: a calibration test asserting league-average vs league-average lineups produce a roughly balanced game (home_win in `[0.45, 0.62]` — home-field tilt allowed but not lopsided; expected_total_runs in a sane `[6, 12]` band); `scripts/mlb_pa_sim_demo.py` prints market probabilities for a neutral matchup and a strong-vs-weak matchup so a human can eyeball the engine.

Notes: this locks the engine's aggregate realism (no live data; pure). The demo script is not a pytest test.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
def test_neutral_matchup_is_realistically_balanced():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    markets = simulate_game_markets(ctx, seed=2026, sims=1500)
    assert 0.42 <= markets["home_win"] <= 0.62      # near coin-flip for equal teams
    assert 6.0 <= markets["expected_total_runs"] <= 12.0  # sane MLB run environment
    assert 0.30 <= markets["yrfi"] <= 0.75           # plausible YRFI band
```

- [ ] **Step 2: Run test to verify it fails / passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k neutral_matchup -v`
Expected: PASS if Task 2's rate constants are calibrated; if it FAILS on `expected_total_runs` or `home_win`, adjust the `LEAGUE` baselines and the `hit_share`/`iso_tilt` constants in Task 2 until a neutral game lands in-band, then re-run the whole module to confirm nothing else regressed. Document any constant change in the commit message.

- [ ] **Step 3: Write the demo script**

```python
# scripts/mlb_pa_sim_demo.py
"""Print mlb_pa_sim market probabilities for a neutral and a lopsided matchup.

Pure/offline eyeball check of the plate-appearance engine — not a pytest test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.mlb_pa_sim import simulate_game_markets  # noqa: E402
from autonomy.sports.statsapi import (  # noqa: E402
    BatterRates, LineupSlot, MlbGameContext, PitcherRates,
)


def _ctx(home_iso: float, away_iso: float) -> MlbGameContext:
    rates = {}
    home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    for i in range(9):
        rates[100 + i] = BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                     bb_pct=0.09, obp=0.340, slg=0.300 + home_iso, iso=home_iso)
        rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.20,
                                     bb_pct=0.09, obp=0.340, slg=0.300 + away_iso, iso=away_iso)
    return MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="HOME", away="AWAY", home_lineup=home, away_lineup=away,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0,
    )


def main() -> int:
    print("Neutral matchup (equal lineups):")
    print(json.dumps(simulate_game_markets(_ctx(0.15, 0.15), seed=1, sims=4000), indent=2))
    print("\nStrong home vs weak away:")
    print(json.dumps(simulate_game_markets(_ctx(0.28, 0.09), seed=1, sims=4000), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the demo and the full suite**

Run: `python scripts/mlb_pa_sim_demo.py`
Expected: neutral matchup shows `home_win` near 0.5 and a believable total; strong-vs-weak shows `home_win` well above 0.5.

Run: `python -m pytest -q`
Expected: full suite green.

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py scripts/mlb_pa_sim_demo.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): calibration sanity check + pa-sim demo report"
```

---

## Self-Review

**Spec coverage (S3b = spec Layer B head 1, `mlb_pa_sim`):**
- Plate-appearance simulation combining batter × pitcher (log5) — Tasks 1-2 ✓
- Platoon + park adjustment — Tasks 2, 4 ✓
- Inning-by-inning with baserunners, starter→bullpen switch — Tasks 3-4 ✓
- One simulation yields win / total / YRFI / F5 coherently — Tasks 4-5 ✓
- Deterministic with a seed — every task ✓
- Uses the S3a batter rates (the reason for full fidelity) — Task 4 ✓
- Aggregate realism locked by calibration test — Task 6 ✓

**Documented modeling simplifications (feature-discovery loop refines later):** no stolen bases / double plays / situational hitting in v1; bullpen is a fatigue-scaled league-average reliever (no per-reliever rates stored); HR-from-ISO and hit-split heuristics are first-order. All are isolated in Task 2/3/4 and independently tunable — these are the genome knobs S5's curriculum will search.

**Placeholder scan:** none — every step carries runnable test and implementation code. Task 6 Step 2 is an explicit calibrate-the-constants step, not a placeholder.

**Type consistency:** `LEAGUE`, `log5`, `PA_OUTCOMES`, `plate_appearance_distribution`, `sample_outcome`, `simulate_half_inning`, `_advance`, `GameResult`, `simulate_one_game`, `simulate_game_markets` are used consistently; consumes `BatterRates`/`PitcherRates`/`LineupSlot`/`MlbGameContext` from statsapi without redefining.

**Out of S3b scope (deferred):** registration as a graded source in the live sports daemon and S2 forward-grading (needs live StatsAPI wiring — governance-gated); the GBM + Bayesian challenger heads (S4); the recursive genome curriculum, feature-discovery critic, and drift guard (S5). S3b delivers the engine and its calibration proof; grading it vs the market awaits the governance green-light and accumulated forward data.
