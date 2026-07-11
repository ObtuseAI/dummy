# Weather → Sports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire Dummy's weather *prediction* (a data-proven net loser vs the sharp Kalshi weather market) and repurpose the keyless Open-Meteo pipeline as an MLB game-time *feature*: fetch ballpark wind + temperature at first pitch and turn them into an HR/run modifier the plate-appearance simulator already knows how to consume.

**Architecture:** (1) Drop `Vertical.WEATHER` from the scanner's default trading verticals so no weather market is scanned/forecast/traded (the ticker→WEATHER classifier stays, for clean exclusion). (2) A new `autonomy/sports/ballpark_weather.py`: an MLB ballpark table (lat/lon + home-plate→CF compass bearing), a keyless Open-Meteo hourly fetch for the park at first pitch, and a pure converter from (temp, wind speed, wind direction) to a `weather_hr_factor` and `weather_run_factor`. (3) Thread those factors into `autonomy/sports/mlb_pa_sim.py` in the same slot as `park_hr_factor`. Neutral weather ⇒ factors of 1.0 ⇒ identical output (so all S3b calibration/tests are preserved).

**Tech Stack:** Python 3.11+, `httpx` (existing), `pytest`. Open-Meteo is keyless/public — NOT the governance-gated `statsapi.mlb.com`, so live use is fine.

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` in new modules.
- Keyless, read-only Open-Meteo HTTP via an injectable fetcher defaulting to the real one; all converter/table tests hermetic (no network). Mirror the `weather_openmeteo.default_fetch_daily_temps` idiom (httpx GET, timeout).
- Pure converters; deterministic. No forecaster/ledger writes. Neutral inputs (≈70°F, calm wind) produce factors of exactly 1.0 so the simulator's existing calibration is unchanged.
- Edits confined to: `autonomy/scanner.py` (Task 1), new `autonomy/sports/ballpark_weather.py` (Tasks 2-3), `autonomy/sports/mlb_pa_sim.py` (Task 4), `scripts/` (Task 5), and their tests. Do not touch the weather *prediction* modules' internals (`weather_openmeteo.py`, `weather_calibration.py`) beyond what Task 1 requires.
- Run the full suite `python -m pytest -q` before the final commit; it must stay green (baseline after PR #18 merge: 4,721 passed, 0 skipped).
- Commit after every task with a message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Retire weather from the trading verticals

**Files:**
- Modify: `autonomy/scanner.py`
- Test: `tests/test_autonomy_pipeline.py` (or the scanner's existing test file)

**Interfaces:**
- Change: the `MarketScanner.__init__` default `verticals` set drops `Vertical.WEATHER` (leaving CRYPTO, SPORTS, COMMODITIES, ECON). The `SERIES_VERTICALS` KXHIGH/KXLOW/KXRAIN/KXSNOW→WEATHER mapping stays so weather tickers still classify (and are therefore excluded by the vertical filter).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_pipeline.py (append)
def test_scanner_no_longer_trades_weather_by_default():
    from autonomy.scanner import MarketScanner
    from autonomy.ontology import Vertical
    scanner = MarketScanner(fetch_series=lambda s: {"markets": []})
    assert Vertical.WEATHER not in scanner.verticals
    # The other verticals remain tradable.
    assert Vertical.SPORTS in scanner.verticals
    assert Vertical.CRYPTO in scanner.verticals


def test_scanner_excludes_weather_market_when_scanned():
    from autonomy.scanner import MarketScanner
    from autonomy.ontology import Vertical
    weather_page = {"markets": [{
        "ticker": "KXHIGHNY-26JUL11-T85", "status": "active",
        "yes_bid": 40, "yes_ask": 42, "no_bid": 58, "no_ask": 60,
    }]}
    scanner = MarketScanner(
        fetch_series=lambda s: weather_page, watchlist=["KXHIGHNY"],
    )
    views = scanner.scan()
    # A weather market still classifies as WEATHER but is filtered out of the scan.
    assert all(v.vertical is not Vertical.WEATHER for v in views)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_pipeline.py -k "no_longer_trades_weather or excludes_weather" -v`
Expected: FAIL (WEATHER still in the default set / weather market still returned).

- [ ] **Step 3: Make the change**

In `autonomy/scanner.py`, the `MarketScanner.__init__` default:

```python
        self.verticals = verticals or {Vertical.CRYPTO, Vertical.SPORTS,
                                       Vertical.COMMODITIES, Vertical.ECON}
```

(Remove `Vertical.WEATHER`. Leave `SERIES_VERTICALS` — the KXHIGH/KXLOW/KXRAIN/KXSNOW classification — untouched.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_autonomy_pipeline.py -k "no_longer_trades_weather or excludes_weather" -v` (PASS), then the whole file to confirm no scanner test regressed.
Expected: PASS. If a pre-existing test asserted weather IS scanned, update it to reflect the retirement (weather is deliberately no longer traded) — that is an intended behavior change, documented in the commit.

- [ ] **Step 5: Commit**

```bash
git add autonomy/scanner.py tests/test_autonomy_pipeline.py
git commit -m "feat(autonomy): retire weather from trading verticals (net loser vs sharp Kalshi)"
```

---

### Task 2: Ballpark table + Open-Meteo hourly fetch

**Files:**
- Create: `autonomy/sports/ballpark_weather.py`
- Test: `tests/test_autonomy_ballpark_weather.py`

**Interfaces:**
- Produces: `BALLPARKS: dict[str, Ballpark]` (team abbrev → `Ballpark(name, lat, lon, cf_bearing_deg, is_dome)`), covering the 30 MLB parks; `GameWeather` dataclass (`temperature_f`, `wind_speed_mph`, `wind_direction_deg`, source provenance); `default_fetch_hourly_weather(lat, lon, date_iso, hour_utc) -> dict` (keyless Open-Meteo hourly GET for `temperature_2m`, `wind_speed_10m`, `wind_direction_10m`); `parse_hourly_weather(payload, hour_index) -> GameWeather | None`.

Notes: Open-Meteo hourly endpoint is `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m,wind_speed_10m,wind_direction_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&start_date=..&end_date=..`. The `cf_bearing_deg` is the compass bearing from home plate toward center field (used in Task 3 to project wind onto the out-to-CF axis). Domes (`is_dome=True`) always return neutral weather.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_ballpark_weather.py
from __future__ import annotations

from autonomy.sports.ballpark_weather import (
    BALLPARKS, GameWeather, parse_hourly_weather,
)


def test_ballpark_table_covers_all_30_teams():
    assert len(BALLPARKS) == 30
    coors = BALLPARKS["COL"]
    assert coors.is_dome is False
    assert 39.0 < coors.lat < 40.0 and -105.5 < coors.lon < -104.5
    assert 0.0 <= coors.cf_bearing_deg < 360.0
    # A dome exists and is flagged.
    assert BALLPARKS["TB"].is_dome is True


_HOURLY_FIXTURE = {
    "hourly": {
        "time": ["2026-07-11T22:00", "2026-07-11T23:00"],
        "temperature_2m": [88.0, 90.0],
        "wind_speed_10m": [12.0, 14.0],
        "wind_direction_10m": [180.0, 200.0],
    }
}


def test_parse_hourly_weather_reads_the_right_hour():
    gw = parse_hourly_weather(_HOURLY_FIXTURE, 1)
    assert gw.temperature_f == 90.0
    assert gw.wind_speed_mph == 14.0
    assert gw.wind_direction_deg == 200.0


def test_parse_hourly_weather_tolerates_missing():
    assert parse_hourly_weather({"hourly": {}}, 0) is None
    assert parse_hourly_weather(_HOURLY_FIXTURE, 99) is None  # out of range
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_ballpark_weather.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

Create `autonomy/sports/ballpark_weather.py` with a `Ballpark` frozen dataclass, the 30-park `BALLPARKS` table (real lat/lon; `cf_bearing_deg` from each park's known orientation; `is_dome=True` for the fixed/retractable-when-typically-closed parks — TB Tropicana, plus AZ/MIL/HOU/TEX/SEA/TOR retractables can be `is_dome=False` with a note, but TB is the clear always-dome), a `GameWeather` frozen dataclass, `default_fetch_hourly_weather` (keyless httpx GET to the Open-Meteo hourly endpoint, `timeout=20`, `raise_for_status`), and `parse_hourly_weather(payload, hour_index)` returning `GameWeather` or `None` when the arrays are missing/short. Every field defensively parsed. (Full table + code written in this task.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_autonomy_ballpark_weather.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/ballpark_weather.py tests/test_autonomy_ballpark_weather.py
git commit -m "feat(mlb): ballpark table + Open-Meteo hourly weather fetch"
```

---

### Task 3: Weather → HR/run factor converter

**Files:**
- Modify: `autonomy/sports/ballpark_weather.py`
- Test: `tests/test_autonomy_ballpark_weather.py`

**Interfaces:**
- Produces: `weather_factors(weather: GameWeather | None, cf_bearing_deg: float, *, is_dome: bool = False) -> tuple[float, float]` returning `(hr_factor, run_factor)`. Neutral (≈70°F, calm) ⇒ `(1.0, 1.0)`. A dome ⇒ `(1.0, 1.0)`. Warmer air raises both modestly; wind projected onto the home-plate→CF axis raises HR when blowing out and lowers it when blowing in.

Notes (documented, conservative — the feature-discovery loop refines later):
- Temperature: `run_factor *= 1 + (temp_f - 70) * 0.006`; `hr_factor *= 1 + (temp_f - 70) * 0.010` (warm, thin air carries the ball). Clamp both to `[0.85, 1.20]`.
- Wind: project onto the out-to-CF axis — `out_component = wind_speed * cos(radians(wind_direction_deg - cf_bearing_deg))` (positive = blowing out toward CF). `hr_factor *= 1 + out_component * 0.010` (≈ +1% HR per mph of out-blowing wind), clamped. Wind has a smaller `run_factor` effect (`* 0.004`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_ballpark_weather.py (append)
from autonomy.sports.ballpark_weather import weather_factors


def test_neutral_and_dome_weather_are_identity():
    neutral = GameWeather(temperature_f=70.0, wind_speed_mph=0.0, wind_direction_deg=0.0)
    assert weather_factors(neutral, cf_bearing_deg=0.0) == (1.0, 1.0)
    assert weather_factors(None, cf_bearing_deg=90.0) == (1.0, 1.0)
    hot = GameWeather(temperature_f=95.0, wind_speed_mph=20.0, wind_direction_deg=0.0)
    assert weather_factors(hot, cf_bearing_deg=0.0, is_dome=True) == (1.0, 1.0)


def test_hot_weather_raises_both_factors():
    hot = GameWeather(temperature_f=95.0, wind_speed_mph=0.0, wind_direction_deg=0.0)
    hr, run = weather_factors(hot, cf_bearing_deg=0.0)
    assert hr > 1.0 and run > 1.0


def test_wind_out_to_center_raises_hr_more_than_wind_in():
    # cf_bearing 0 (CF is due north). Wind FROM 0deg blows toward 180 (in from CF);
    # wind FROM 180 blows toward 0 (out to CF).
    out = GameWeather(temperature_f=70.0, wind_speed_mph=15.0, wind_direction_deg=180.0)
    into = GameWeather(temperature_f=70.0, wind_speed_mph=15.0, wind_direction_deg=0.0)
    hr_out, _ = weather_factors(out, cf_bearing_deg=0.0)
    hr_in, _ = weather_factors(into, cf_bearing_deg=0.0)
    assert hr_out > 1.0 > hr_in
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_ballpark_weather.py -k "neutral_and_dome or hot_weather or wind_out" -v`
Expected: FAIL (`ImportError: weather_factors`).

- [ ] **Step 3: Write the implementation** (per the Notes formulas, with clamps; neutral/None/dome short-circuit to `(1.0, 1.0)`; `import math` for the wind projection).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_autonomy_ballpark_weather.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/ballpark_weather.py tests/test_autonomy_ballpark_weather.py
git commit -m "feat(mlb): weather -> HR/run factor converter (temp + wind projection)"
```

---

### Task 4: Wire weather into the plate-appearance simulator

**Files:**
- Modify: `autonomy/sports/mlb_pa_sim.py`
- Test: `tests/test_autonomy_mlb_pa_sim.py`

**Interfaces:**
- Change: `plate_appearance_distribution` gains a `weather_hr_factor: float = 1.0` (multiplies the HR term alongside `park_hr_factor`); `simulate_one_game`/`simulate_game_markets` accept an optional `weather: tuple[float, float] | None = None` = `(hr_factor, run_factor)`; the `run_factor` scales the offense multiplier (like HFA) and the `hr_factor` threads to the HR term. `weather=None` ⇒ no change (all existing tests pass unchanged).

Notes: keep it minimal — the simulator stays pure; the caller (a later live-wiring step, governance-independent since Open-Meteo is keyless) passes the factors from `ballpark_weather.weather_factors`. This task only makes the simulator *able* to consume weather; it does not fetch anything.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_pa_sim.py (append)
def test_weather_hr_factor_raises_home_runs():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    calm = simulate_game_markets(ctx, seed=5, sims=800, weather=None)
    windy = simulate_game_markets(ctx, seed=5, sims=800, weather=(1.30, 1.05))
    assert windy["expected_total_runs"] > calm["expected_total_runs"]


def test_weather_none_is_unchanged():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    a = simulate_game_markets(ctx, seed=5, sims=500)
    b = simulate_game_markets(ctx, seed=5, sims=500, weather=None)
    assert a == b  # weather=None is a no-op, preserving all S3b calibration
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -k "weather_hr_factor or weather_none" -v`
Expected: FAIL (`simulate_game_markets` has no `weather` kwarg).

- [ ] **Step 3: Write the implementation** — thread `weather` through `simulate_game_markets` → `simulate_one_game` → the distribution builders: apply `run_factor` as an extra `offense_mult` on both sides and `hr_factor` as `weather_hr_factor` into `plate_appearance_distribution` (multiplying the HR term). `weather=None` ⇒ `(1.0, 1.0)`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_autonomy_mlb_pa_sim.py -v`
Expected: all PASS — the two new tests plus every existing calibration/composition test unchanged (because `weather=None` is a no-op).

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q` (full suite green, >= 4,721 + new tests).

```bash
git add autonomy/sports/mlb_pa_sim.py tests/test_autonomy_mlb_pa_sim.py
git commit -m "feat(mlb): plate-appearance sim consumes ballpark weather factors"
```

---

### Task 5: Live verification against a real park

**Files:**
- Create: `scripts/verify_ballpark_weather_live.py`

**Interfaces:**
- Consumes: `BALLPARKS`, `default_fetch_hourly_weather`, `parse_hourly_weather`, `weather_factors`.

Notes: read-only, keyless. For a couple of real parks (e.g. `COL` Coors, `NYY`), fetch tonight's first-pitch-hour Open-Meteo forecast, print the observed temp/wind and the derived `(hr_factor, run_factor)`. Proves the pipeline end to end. Not a pytest test.

- [ ] **Step 1: Write the script** (sys.path shim; fetch for 2-3 parks at ~19:00 local → UTC hour; print weather + factors; dome parks print `(1.0, 1.0)`).

- [ ] **Step 2: Run it against the live Open-Meteo API**

Run: `python scripts/verify_ballpark_weather_live.py`
Expected: prints real temp/wind for the parks and plausible factors (Coors on a warm day → hr_factor > 1). Must not raise.

- [ ] **Step 3: Run the full suite for regression**

Run: `python -m pytest -q`
Expected: full suite green.

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_ballpark_weather_live.py
git commit -m "feat(mlb): live Open-Meteo ballpark-weather verification script"
```

---

## Self-Review

**Directive coverage:**
- Stop weather prediction — Task 1 (drop the trading vertical) ✓
- Use the weather pipeline for sports — Tasks 2-4 (Open-Meteo → ballpark game weather → HR/run factors → into the PA-sim) ✓
- Keyless/governance-independent (Open-Meteo, not statsapi.mlb.com) — Task 2 ✓
- Non-destructive to S3b calibration (`weather=None` no-op) — Task 4 ✓

**Placeholder scan:** none — each step has runnable tests and concrete formulas; Tasks 2-3-5 note "full table/code/script written in this task" where the body is long but fully specified by the interface + formulas.

**Deferred (feature-discovery loop / later):** per-park wind-tunnel calibration of the coefficients, humidity/air-density refinement, retractable-roof state (currently only the always-dome TB is neutral), and the live wiring that fetches weather per real game and feeds `simulate_game_markets` (a small governance-independent scheduler step once the sim is graded).
