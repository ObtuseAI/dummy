# MLB pa-sim — Times-Through-Order Calibration Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the S3b super-bullpen calibration hack with a physically-correct model: a times-through-order (TTO) penalty raises the starter's run environment as it faces the lineup repeatedly (the real reason late innings score more), a realistic bullpen resets that familiarity, and a home-field term restores the real home edge — then re-calibrate a neutral game to real MLB (total ~8.5, YRFI ~0.55, home_win ~0.54). This is the prerequisite before `mlb_pa_sim` is graded by the S2 harness.

**Architecture:** Edit `autonomy/sports/mlb_pa_sim.py` only. `_side_distributions` gains an `offense_mult` multiplier (folded into the existing platoon term). The starter's per-slot distributions are precomputed at each TTO level (0-3); `_simulate_side` tracks batters faced by the *current* pitcher, raises the TTO level as the starter cycles the order, and on the bullpen switch resets the count (a fresh reliever = a fresh look). Realistic reliever baselines replace `BULLPEN_K_BOOST`/`BULLPEN_BASE_HR9`. A `HOME_FIELD_BOOST` lifts the home lineup's offense. Constants are re-tuned empirically to land a neutral matchup in real-MLB bands. Deterministic and offline throughout.

**Tech Stack:** Python 3.11+, stdlib, `pytest`. No new dependency.

## Global Constraints

- Python `>=3.11`; edit `autonomy/sports/mlb_pa_sim.py` and `tests/test_autonomy_mlb_pa_sim.py`; refresh `scripts/mlb_pa_sim_demo.py` output only if needed. No other file.
- Deterministic (seeded `random.Random`), pure, offline. Never call unseeded `random.*` or time.
- Every outcome distribution still sums to 1.0 (±1e-9) and every probability stays in [0,1] after the changes — the existing invariant tests must keep passing.
- The public signatures `simulate_one_game(context, rng, *, innings=9)` and `simulate_game_markets(context, *, seed, sims, total_line)` do NOT change. Internal helper signatures may change.
- All existing directional tests (strong>weak lineup, park raises HR, slugging raises hits, platoon, pitcher pairing, determinism, base-running truth tables) must stay green; if a directional test breaks, the rework is wrong — do not weaken the test.
- Run the full suite `python -m pytest -q` before the final commit; it must stay green (baseline 4,714).
- Commit after every task with a `fix:`/`feat:`/`test:` message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: TTO penalty mechanism + realistic bullpen

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Changes: add `offense_mult: float = 1.0` to `_side_distributions` (multiplies the platoon term); add `TTO_PENALTY_PER_TIME`, `TTO_MAX_TIMES`, `RELIEVER_K_PCT`, `RELIEVER_BB_PCT`, `RELIEVER_HR9` constants; remove `BULLPEN_K_BOOST`/`BULLPEN_BASE_HR9`; add `_starter_distributions_by_tto(lineup, batter_rates, pitcher, park_hr, offense_mult) -> list[list[dict]]` (index = TTO level 0..TTO_MAX_TIMES); rewrite `_bullpen_distributions` to use the realistic reliever baselines; change `_simulate_side` to take `(starter_by_tto, bullpen_dists, rng, innings)` and track per-pitcher batters-faced, selecting the TTO level for the starter and resetting to a fresh look when the bullpen enters; update `simulate_one_game` to build the TTO-indexed starter sets (home lineup carries the `offense_mult` used later for HFA — pass `1.0` here, HFA arrives in Task 2).

Notes: `tto_mult(level) = 1.0 + TTO_PENALTY_PER_TIME * min(level, TTO_MAX_TIMES)`. Choose `TTO_PENALTY_PER_TIME ≈ 0.04`, `TTO_MAX_TIMES = 3`. Realistic reliever: `RELIEVER_K_PCT ≈ 0.245` (relievers strike out a touch more than the league PA rate), `RELIEVER_BB_PCT ≈ 0.090`, `RELIEVER_HR9 ≈ 1.15` — degraded by aggregate bullpen fatigue as before. `STARTER_BATTERS_FACED` stays ~24 (a real start). Within a half-inning the TTO level is fixed (chosen at inning start from the current per-pitcher faced count); the bullpen switch resets that count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
from autonomy.sports.mlb_pa_sim import (
    RELIEVER_K_PCT, TTO_PENALTY_PER_TIME, _starter_distributions_by_tto,
)


def test_tto_penalty_raises_offense_deeper_into_the_order():
    lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                  bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
             for i in range(9)}
    pitcher = PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2)
    by_tto = _starter_distributions_by_tto(lineup, rates, pitcher, 1.0, 1.0)
    # Third time through the order allows more offense than the first time.
    first_time_hr = sum(d["hr"] for d in by_tto[0])
    third_time_hr = sum(d["hr"] for d in by_tto[3])
    assert third_time_hr > first_time_hr
    assert TTO_PENALTY_PER_TIME > 0.0


def test_realistic_reliever_is_not_cartoonish():
    # The reliever strikes out modestly more than league, not 70% more.
    assert 0.22 <= RELIEVER_K_PCT <= 0.28
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "tto_penalty or realistic_reliever" -v`
Expected: FAIL with `ImportError` (new names not yet defined).

- [ ] **Step 3: Write the implementation**

Replace the constant block and the bullpen/side/simulate helpers. Set the constants:

```python
# autonomy/sports/mlb_pa_sim.py — replace the BULLPEN_* block
STARTER_BATTERS_FACED = 24  # a full modern start before the bullpen takes over
TTO_PENALTY_PER_TIME = 0.04  # each time through the order lifts the batter's offense
TTO_MAX_TIMES = 3            # penalty saturates by the third time through
RELIEVER_K_PCT = 0.245      # relievers strike out modestly more than league
RELIEVER_BB_PCT = 0.090
RELIEVER_HR9 = 1.15
```

Add the TTO multiplier helper and the TTO-indexed starter builder; give `_side_distributions` an `offense_mult`:

```python
def _tto_mult(level: int) -> float:
    return 1.0 + TTO_PENALTY_PER_TIME * min(level, TTO_MAX_TIMES)


def _side_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    pitcher: Any,
    park_hr_factor: float,
    offense_mult: float = 1.0,
) -> list[dict[str, float]]:
    dists: list[dict[str, float]] = []
    throws = getattr(pitcher, "throws", None)
    for slot in lineup:
        batter = batter_rates.get(slot.player_id)
        dists.append(plate_appearance_distribution(
            batter, pitcher,
            park_hr_factor=park_hr_factor,
            platoon=_platoon(getattr(slot, "bats", None), throws) * offense_mult,
        ))
    return dists


def _starter_distributions_by_tto(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    pitcher: Any,
    park_hr_factor: float,
    offense_mult: float,
) -> list[list[dict[str, float]]]:
    """Per-slot distributions for each times-through-the-order level (0..MAX)."""
    return [
        _side_distributions(
            lineup, batter_rates, pitcher, park_hr_factor,
            offense_mult=offense_mult * _tto_mult(level),
        )
        for level in range(TTO_MAX_TIMES + 1)
    ]
```

Rewrite `_bullpen_distributions` to the realistic reliever:

```python
def _bullpen_distributions(
    lineup: tuple[Any, ...],
    batter_rates: dict[int, Any],
    fatigue: dict[int, float],
    park_hr_factor: float,
    offense_mult: float = 1.0,
) -> list[dict[str, float]]:
    avg_fatigue = (sum(fatigue.values()) / len(fatigue)) if fatigue else 0.0
    reliever = PitcherRates(
        player_id=-1, throws=None,
        k_pct=RELIEVER_K_PCT * (1.0 - 0.15 * avg_fatigue),
        bb_pct=RELIEVER_BB_PCT * (1.0 + 0.20 * avg_fatigue),
        hr9=RELIEVER_HR9 * (1.0 + 0.20 * avg_fatigue),
    )
    return _side_distributions(lineup, batter_rates, reliever, park_hr_factor, offense_mult)
```

Rewrite `_simulate_side` to track per-pitcher batters faced, pick the TTO level, and reset on the bullpen switch:

```python
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
```

Update `simulate_one_game` to build the TTO-indexed starter sets (pass `offense_mult=1.0` for now — HFA is Task 2):

```python
def simulate_one_game(
    context: MlbGameContext, rng: random.Random, *, innings: int = 9,
) -> GameResult:
    park_hr = context.park_hr_factor if context.park_hr_factor is not None else 1.0
    home_starter = _starter_distributions_by_tto(
        context.home_lineup, context.batter_rates, context.away_pitcher, park_hr, 1.0)
    home_pen = _bullpen_distributions(
        context.home_lineup, context.batter_rates, context.away_bullpen_fatigue, park_hr)
    away_starter = _starter_distributions_by_tto(
        context.away_lineup, context.batter_rates, context.home_pitcher, park_hr, 1.0)
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

The pre-existing `test_bullpen_fatigue_degrades_run_prevention` test calls `_bullpen_distributions(lineup, rates, fatigue, factor)` with four positional args — the new `offense_mult` default keeps it working. If that test asserted specific K/HR magnitudes tied to the old `BULLPEN_K_BOOST`, update its expected direction (fatigued still > fresh) but not its shape.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "tto_penalty or realistic_reliever" -v` (PASS), then `python -m pytest tests/test_autonomy_mlb_pa_sim.py -v`.
Expected: the two new tests PASS. The Task 6 calibration lock test (`test_neutral_matchup_is_calibrated_to_real_mlb`) will likely FAIL now (the run environment changed) — that is expected and is re-tuned in Task 3. All other directional tests must still pass. If a directional test other than the calibration lock fails, fix the mechanism, not the test.

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "fix(mlb): times-through-order penalty + realistic bullpen (replace super-bullpen)"
```

---

### Task 2: Home-field advantage

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Changes: add `HOME_FIELD_BOOST` constant; in `simulate_one_game`, pass `offense_mult=HOME_FIELD_BOOST` when building the HOME lineup's starter and bullpen distributions (away stays `1.0`).

Notes: real home teams win ~54% of otherwise-even games. A small home-offense multiplier (`HOME_FIELD_BOOST ≈ 1.03`) produces that edge; the exact value is finalized in Task 3's calibration.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
from autonomy.sports.mlb_pa_sim import HOME_FIELD_BOOST


def test_home_field_advantage_favors_the_home_side():
    assert HOME_FIELD_BOOST > 1.0
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)  # identical teams
    markets = simulate_game_markets(ctx, seed=99, sims=1500)
    assert markets["home_win"] > 0.51  # equal teams, but the home side is favored
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k home_field -v`
Expected: FAIL with `ImportError: cannot import name 'HOME_FIELD_BOOST'` (or the assertion fails if the constant exists but is 1.0).

- [ ] **Step 3: Write the implementation**

```python
# autonomy/sports/mlb_pa_sim.py — add near the other constants
HOME_FIELD_BOOST = 1.03  # home lineups score slightly more (finalized in calibration)
```

In `simulate_one_game`, change the two HOME builders to pass the boost:

```python
    home_starter = _starter_distributions_by_tto(
        context.home_lineup, context.batter_rates, context.away_pitcher, park_hr,
        HOME_FIELD_BOOST)
    home_pen = _bullpen_distributions(
        context.home_lineup, context.batter_rates, context.away_bullpen_fatigue, park_hr,
        HOME_FIELD_BOOST)
```

(Leave the two AWAY builders at their `1.0` default.)

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k home_field -v`
Expected: PASS (the calibration lock test remains expected-failing until Task 3).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): home-field advantage term"
```

---

### Task 3: Re-calibrate to real MLB + heterogeneous-lineup lock

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py` (calibration constants only)
- Test: `tests/test_autonomy_mlb_pa_sim.py`
- Refresh: `scripts/mlb_pa_sim_demo.py` output (no structural change required)

**Interfaces:**
- Tune the offense constants (`HIT_SHARE_BASE`, `HR_ISO_MULT`, `HIT_SHARE_CAP`, and if needed `LEAGUE` and `TTO_PENALTY_PER_TIME`/`HOME_FIELD_BOOST`) so a neutral matchup lands in real-MLB bands; replace/extend the calibration lock test.

Notes: with TTO now supplying the late-game lift and a realistic bullpen no longer suppressing runs, the offense base likely needs to come DOWN from the Task 6 hack values. Iterate empirically.

- [ ] **Step 1: Update the calibration lock test to real-MLB bands (and add a heterogeneous lineup)**

Replace `test_neutral_matchup_is_calibrated_to_real_mlb` with:

```python
def test_neutral_matchup_is_calibrated_to_real_mlb():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    m = simulate_game_markets(ctx, seed=2026, sims=3000)
    assert 8.0 <= m["expected_total_runs"] <= 9.2   # real MLB ~8.5 total
    assert 0.50 <= m["yrfi"] <= 0.62                 # real MLB YRFI ~0.55
    assert 0.51 <= m["home_win"] <= 0.575            # home edge ~0.54


def test_heterogeneous_lineup_still_realistic_totals():
    # A real lineup is not uniform: a strong top, weak bottom. Totals must stay sane.
    lineup_iso = [0.24, 0.22, 0.26, 0.20, 0.16, 0.13, 0.11, 0.09, 0.08]
    home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    rates = {}
    for i, iso in enumerate(lineup_iso):
        rates[100 + i] = BatterRates(player_id=100 + i, bats="R", k_pct=0.21,
                                     bb_pct=0.085, obp=0.320 + iso * 0.2,
                                     slg=0.360 + iso, iso=iso)
        rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.21,
                                     bb_pct=0.085, obp=0.320 + iso * 0.2,
                                     slg=0.360 + iso, iso=iso)
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="H", away="A", home_lineup=home, away_lineup=away,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0)
    m = simulate_game_markets(ctx, seed=7, sims=2000)
    assert 6.5 <= m["expected_total_runs"] <= 10.5   # sane real-MLB run band
    assert 0.0 <= m["yrfi"] <= 1.0
```

- [ ] **Step 2: Run it and tune the constants until it passes**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "neutral_matchup or heterogeneous" -v`
Expected: initially FAIL. Adjust `HIT_SHARE_BASE`/`HR_ISO_MULT`/`HIT_SHARE_CAP` (and, only if necessary, `LEAGUE["out"]` with a compensating change so `LEAGUE` still sums to 1.0, or `TTO_PENALTY_PER_TIME`/`HOME_FIELD_BOOST`) and re-run until both tests pass. Keep changes small and re-run the WHOLE module after each to confirm no directional test regressed. Document the final constants in the commit message.

- [ ] **Step 3: Refresh the demo and eyeball it**

Run: `python scripts/mlb_pa_sim_demo.py`
Expected: neutral matchup shows `home_win` ~0.54, `expected_total_runs` ~8.5, `yrfi` ~0.55; strong-vs-weak shows a clear home edge. No code change needed unless the script hard-codes stale numbers in comments.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: full suite green (>= 4,714 passed, 0 skipped).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "fix(mlb): re-calibrate pa-sim to real MLB with TTO + HFA + realistic bullpen"
```

---

## Self-Review

**Coverage of the review findings this rework addresses:**
- Super-bullpen inverting the inning run-shape → replaced by TTO on the starter + realistic reliever (Task 1) ✓
- No home-field advantage → `HOME_FIELD_BOOST` (Task 2) ✓
- Homogeneous-lineup calibration masking the top-of-order effect → heterogeneous-lineup lock test (Task 3) ✓
- Right inning-by-inning run *shape*, not just the right aggregate → TTO makes late innings score more via the physically-correct mechanism (Task 1) ✓

**Placeholder scan:** none — Task 3's tune-the-constants step is an explicit empirical calibration loop with concrete target bands, not a placeholder.

**Type consistency:** `_tto_mult`, `_starter_distributions_by_tto`, the extended `_side_distributions`/`_bullpen_distributions`, and the rewritten `_simulate_side` are used consistently; `simulate_one_game`/`simulate_game_markets` public signatures unchanged.

**Still deferred (not this rework):** per-reliever rates (bullpen quality as a tradeable edge — needs stored reliever data); station-to-station single under-conversion; walk-off/extra-innings truncation; `park_run_factor` wiring (a separate small follow-up). These remain documented S4/S5 or minor-follow-up items.
