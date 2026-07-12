# MLB Matchup Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MLB plate-appearance simulator aware of (1) real per-player left/right platoon splits (replacing the flat 0.93/1.07 multiplier), (2) real per-team bullpen quality (replacing the league-average reliever), and (3) rivalry/divisional matchups — each non-destructively (missing data falls back to today's behavior, byte-identical, preserving the calibration).

**Architecture:** `autonomy/sports/statsapi.py` gains handedness-split fetch/parse (nested `vs_lhp`/`vs_rhp` on `BatterRates`, `vs_lhb`/`vs_rhb` on `PitcherRates`) and a per-team bullpen aggregate on `MlbGameContext`. `autonomy/sports/mlb_pa_sim.py` resolves each matchup to the batter's/pitcher's real split rates when present (else the flat `_platoon` fallback), uses the team bullpen rate when present (else the league-average reliever), and applies a small divisional/rivalry variance bump. A new tiny `autonomy/sports/mlb_matchups.py` holds the static division/rivalry table.

**Tech Stack:** Python 3.11+, `httpx` (existing), `pytest`. StatsAPI splits via `hydrate=stats(group=[hitting|pitching],type=[statSplits],sitCodes=[vl,vr])` (keyless). Open-Meteo-style injectable fetchers; hermetic parser tests.

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations`.
- Keyless read-only StatsAPI via injectable fetchers (real default); parser tests hermetic (fixture in, dataclass out, no network).
- NON-DESTRUCTIVE: a batter with no split data uses the flat `_platoon` (today's behavior); a game with no team-bullpen data uses the league-average reliever (today's behavior); a non-divisional game gets no bump. The neutral/no-extra-data path must stay byte-identical, so `test_neutral_matchup_is_calibrated_to_real_mlb` and `test_neutral_run_composition_is_realistic` pass UNCHANGED.
- Every rate field nullable; missing splits/bullpen → None, never raises. Reuse the module's `_float`/`_rate` helpers.
- Public simulator signatures stay backward-compatible (new context fields default empty/None).
- Full suite `python -m pytest -q` green before the final commit (baseline after PR #19 merge: 4,731 passed, 0 skipped).
- Commit after every task with the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: Handedness-split rates on BatterRates / PitcherRates

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- `BatterRates` gains `vs_lhp: BatterRates | None = None`, `vs_rhp: BatterRates | None = None` (nested rates vs left/right pitching). `PitcherRates` gains `vs_lhb: PitcherRates | None = None`, `vs_rhb: PitcherRates | None = None`. All default None (backward-compatible; `field_provenance` already treats None as absent).
- Produces: `batter_rates_vs(batter: BatterRates | None, pitcher_throws: str | None) -> BatterRates | None` (returns the split vs the pitcher's hand when present, else the overall batter, else None); `pitcher_rates_vs(pitcher: PitcherRates | None, batter_bats: str | None) -> PitcherRates | None` (symmetric; switch-hitter batter → overall).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import batter_rates_vs, pitcher_rates_vs


def test_batter_rates_vs_selects_split_by_pitcher_hand():
    from autonomy.sports.statsapi import BatterRates
    vs_l = BatterRates(player_id=1, k_pct=0.15, bb_pct=0.12, obp=0.380, slg=0.520, iso=0.24)
    vs_r = BatterRates(player_id=1, k_pct=0.24, bb_pct=0.07, obp=0.300, slg=0.400, iso=0.14)
    batter = BatterRates(player_id=1, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450,
                         iso=0.18, vs_lhp=vs_l, vs_rhp=vs_r)
    assert batter_rates_vs(batter, "L").obp == 0.380   # facing a lefty -> vs-LHP split
    assert batter_rates_vs(batter, "R").obp == 0.300   # facing a righty -> vs-RHP split
    # No split populated -> fall back to the overall line.
    plain = BatterRates(player_id=2, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450, iso=0.18)
    assert batter_rates_vs(plain, "L").obp == 0.340
    assert batter_rates_vs(None, "L") is None


def test_pitcher_rates_vs_selects_split_by_batter_hand():
    from autonomy.sports.statsapi import PitcherRates
    vs_l = PitcherRates(player_id=3, k_pct=0.30, bb_pct=0.06, hr9=0.9)
    vs_r = PitcherRates(player_id=3, k_pct=0.20, bb_pct=0.09, hr9=1.4)
    pitcher = PitcherRates(player_id=3, k_pct=0.25, bb_pct=0.08, hr9=1.1,
                           vs_lhb=vs_l, vs_rhb=vs_r)
    assert pitcher_rates_vs(pitcher, "L").hr9 == 0.9
    assert pitcher_rates_vs(pitcher, "R").hr9 == 1.4
    assert pitcher_rates_vs(pitcher, "S").hr9 == 1.1   # switch hitter -> overall
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k "rates_vs" -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write the implementation**

Add the nested fields to `BatterRates` and `PitcherRates` (self-referential defaults `= None`). Then:

```python
def batter_rates_vs(batter: BatterRates | None, pitcher_throws: str | None) -> BatterRates | None:
    if batter is None:
        return None
    if pitcher_throws == "L" and batter.vs_lhp is not None:
        return batter.vs_lhp
    if pitcher_throws == "R" and batter.vs_rhp is not None:
        return batter.vs_rhp
    return batter


def pitcher_rates_vs(pitcher: PitcherRates | None, batter_bats: str | None) -> PitcherRates | None:
    if pitcher is None:
        return None
    if batter_bats == "L" and pitcher.vs_lhb is not None:
        return pitcher.vs_lhb
    if batter_bats == "R" and pitcher.vs_rhb is not None:
        return pitcher.vs_rhb
    return pitcher
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_autonomy_statsapi.py -k "rates_vs" -v` (PASS), then the whole statsapi module (S1/S3a unchanged).

- [ ] **Step 5: Commit** `feat(mlb): handedness-split rate fields + split resolvers`

---

### Task 2: Parse + hydrate handedness splits from StatsAPI

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- `parse_batter_splits(people_payload) -> tuple[BatterRates | None, BatterRates | None]` (vs-LHP, vs-RHP from a `statSplits` payload whose `splits` carry `split.code` in {"vl","vr"}); `parse_pitcher_splits(people_payload) -> tuple[PitcherRates | None, PitcherRates | None]` (vs-LHB, vs-RHB). `StatsApiClient` fetches splits (new `fetch_batter_splits`/`fetch_pitcher_splits` injectable fetchers, default real, `sitCodes=[vl,vr]`) and attaches them into the `vs_*` fields during hydration; a split fetch that fails is swallowed (splits stay None), never crashing hydration.

- [ ] **Step 1: Write the failing test** (fixture with a `statSplits` payload containing `splits: [{"split":{"code":"vl"},"stat":{...}}, {"split":{"code":"vr"},"stat":{...}}]`; assert `parse_batter_splits` returns two `BatterRates` with the right rates, and returns `(None, None)` on an empty/missing payload).

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** `parse_batter_splits`/`parse_pitcher_splits` (reuse `_rate`/`_float`; iterate `stats[0].splits`, key by `split.code`), the two `default_fetch_*_splits` fetchers (httpx GET, `hydrate=stats(group=[hitting|pitching],type=[statSplits],sitCodes=[vl,vr])`, `timeout=20`, `raise_for_status`), and extend `StatsApiClient._batter`/`_pitcher` (or the hydration path) to fetch splits and produce a `replace(rates, vs_lhp=.., vs_rhp=..)`; wrap the split fetch in the existing swallow-to-None try/except.

- [ ] **Step 4: Run tests** — splits tests PASS; whole statsapi module green.

- [ ] **Step 5: Commit** `feat(mlb): parse + hydrate StatsAPI handedness splits`

---

### Task 3: Simulator uses real platoon splits (flat multiplier only as fallback)

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- In `_side_distributions`, for each batter facing the pitcher: resolve `eff_batter = batter_rates_vs(batter, pitcher_throws)` and `eff_pitcher = pitcher_rates_vs(pitcher, batter_bats)`; when EITHER real split was applied, call `plate_appearance_distribution(eff_batter, eff_pitcher, ..., platoon=1.0)` (the real split already encodes the platoon effect); when NO split data exists for the batter, keep the current flat `_platoon(...)` multiplier. Net: split-aware players get real matchup rates; split-less players are byte-identical to today.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
def test_extreme_platoon_split_batter_uses_real_rates():
    # A batter who crushes RHP but is weak vs LHP should score much more vs a RHP
    # starter than the flat 7% platoon bump would ever produce.
    from autonomy.sports.statsapi import BatterRates, LineupSlot, MlbGameContext, PitcherRates
    strong_vs_r = BatterRates(player_id=1, bats="L", k_pct=0.12, bb_pct=0.14,
                              obp=0.420, slg=0.620, iso=0.30)
    weak_vs_l = BatterRates(player_id=1, bats="L", k_pct=0.30, bb_pct=0.05,
                            obp=0.280, slg=0.330, iso=0.09)
    split_batter = BatterRates(player_id=1, bats="L", k_pct=0.20, bb_pct=0.10,
                               obp=0.350, slg=0.470, iso=0.20,
                               vs_lhp=weak_vs_l, vs_rhp=strong_vs_r)
    def ctx(pitcher_throws):
        rates = {100 + i: split_batter for i in range(9)}
        home = tuple(LineupSlot(i + 1, 100 + i, bats="L") for i in range(9))
        away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
        for i in range(9):
            rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.22,
                                         bb_pct=0.08, obp=0.320, slg=0.400, iso=0.14)
        return MlbGameContext(
            game_pk=1, snapshot="confirmed", captured_at="x", home="H", away="A",
            home_lineup=home, away_lineup=away,
            home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
            away_pitcher=PitcherRates(player_id=8, throws=pitcher_throws, k_pct=0.22, bb_pct=0.08, hr9=1.2),
            batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0)
    vs_rhp = sum(simulate_one_game(ctx("R"), _random.Random(s)).home_runs for s in range(60))
    vs_lhp = sum(simulate_one_game(ctx("L"), _random.Random(s)).home_runs for s in range(60))
    assert vs_rhp > vs_lhp * 1.3   # real split >> flat 7% platoon swing
```

- [ ] **Step 2-4:** run/fail, implement (resolve `eff_batter`/`eff_pitcher`, `platoon=1.0` when split applied else flat `_platoon`), confirm the new test passes AND every existing calibration/composition test is UNCHANGED (split-less neutral fixtures still use the flat path).

- [ ] **Step 5: Commit** `feat(mlb): simulator uses real handedness splits with flat-platoon fallback`

---

### Task 4: Per-team bullpen quality

**Files:**
- Modify: `autonomy/sports/statsapi.py` (bullpen fetch/parse + context fields), `autonomy/sports/mlb_pa_sim.py` (use it)
- Test: both test files

**Interfaces:**
- `MlbGameContext` gains `home_bullpen_rates: PitcherRates | None = None`, `away_bullpen_rates: PitcherRates | None = None` (the team's aggregate relief-pitching rate). `parse_team_bullpen(payload) -> PitcherRates | None` from a team relief-pitching split (`sitCodes=[relief]` or team pitching split). `StatsApiClient.hydrate_bullpen(ctx)` fills them (injectable fetcher, swallow-to-None). In `mlb_pa_sim._bullpen_distributions`, use the passed team bullpen `PitcherRates` when present; else the league-average `RELIEVER_*` constants (today's behavior). Thread `home_bullpen_rates`/`away_bullpen_rates` through `simulate_one_game`.

- [ ] Steps 1-5 (TDD): a test that a strong team bullpen (high K, low HR9) suppresses runs vs a weak one across seeds; a test that `bullpen_rates=None` is byte-identical to today's league-average path; parse/hydrate defensive tests. Commit `feat(mlb): per-team bullpen quality in the simulator`.

---

### Task 5: Rivalry / divisional awareness

**Files:**
- Create: `autonomy/sports/mlb_matchups.py`
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_matchups.py`, `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- `DIVISIONS: dict[str, str]` (team → division, e.g. "NYY"→"AL East"); `RIVALRIES: frozenset[frozenset[str]]` (known rivalry pairs, e.g. {NYY,BOS}, {LAD,SF}, {CHC,STL}); `is_divisional(home, away) -> bool`; `is_rivalry(home, away) -> bool`. `simulate_game_markets` gains `divisional: bool = False` which applies a modest variance bump (divisional/rivalry games are historically closer/higher-variance): widen per-game run variance slightly so `home_win` regresses a touch toward 0.5. `divisional=False` (default) = byte-identical to today.

- [ ] Steps 1-5 (TDD): `is_divisional`/`is_rivalry` truth tests over the table; a test that `divisional=True` pulls a lopsided matchup's `home_win` modestly toward 0.5 vs `divisional=False`; `divisional=False` unchanged. Commit `feat(mlb): rivalry/divisional matchup awareness`.

---

### Task 6: Non-destructive guard + live verification

**Files:**
- Modify: `tests/test_autonomy_mlb_pa_sim.py`
- Create: `scripts/verify_mlb_matchup_intelligence_live.py`

**Interfaces:**
- A regression test asserting that a fully split-less, bullpen-less, non-divisional context produces EXACTLY today's calibrated numbers (the composition/calibration locks already do this, but add one explicit "all intelligence absent == baseline" assertion). A live script that, for a real game, fetches splits + team bullpen and prints the resolved matchup rates (proving the StatsAPI split/bullpen fetch works end to end; keyless, read-only, dome/None-safe).

- [ ] Steps: add the guard test; write + run the live script (record actual output); full suite green. Commit `feat(mlb): matchup-intelligence non-destructive guard + live verify`.

---

## Self-Review

**Directive coverage:**
- L/R matchups with real historical splits — Tasks 1-3 ✓
- Good/bad bullpens — Task 4 ✓
- Rivalries + divisional — Task 5 ✓
- Non-destructive (missing data == today's calibrated behavior) — every task's fallback + Task 6 guard ✓

**Placeholder scan:** Tasks 2/4/5 compress the routine parse/fetch/table bodies under their interface + TDD spec (the shape mirrors S1/S3a's already-built parsers); no "TBD". **Type consistency:** `batter_rates_vs`/`pitcher_rates_vs`, the nested `vs_*` fields, `parse_*_splits`, `parse_team_bullpen`, `DIVISIONS`/`is_divisional`/`is_rivalry` used consistently.

**Governance:** StatsAPI is keyless but `statsapi.mlb.com` is terms-flagged (BLOCKED_TERMS_UNCLEAR) — build/test offline; the live verify script (Task 6) is a manual read-only check, and live per-game wiring stays gated behind the operator terms review.

**Deferred:** per-batter-vs-specific-pitcher history (beyond L/R aggregate), reliever-by-reliever leverage modeling, rivalry intensity weighting, and the coefficient tuning of the divisional variance bump (feature-discovery loop).
