# MLB Monster S1 — StatsAPI Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the official, keyless MLB StatsAPI into a point-in-time `MlbGameContext` (lineups, platoon splits, bullpen fatigue, park factors, pitcher rates, wind/temp) with two pre-game snapshots, so later model heads have market-beating inputs with lookahead-free provenance.

**Architecture:** A new `autonomy/sports/statsapi.py` mirrors the existing `espn.py` idiom — a real `default_fetch_*` callable (injectable for hermetic tests), pure `parse_*` functions, and a thin client with a per-cycle cache. It produces `MlbGameContext` (every field nullable + a `fields_present` provenance map). No model or signal wiring in S1 — that is S3. The existing ESPN `Game` remains the fallback and is untouched.

**Tech Stack:** Python 3.11+, `httpx` (already a runtime dep), `dataclasses`, `pytest`. Official endpoints under `https://statsapi.mlb.com/api/v1` (no key, no auth).

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` at the top of every new module (matches repo style).
- Keyless, read-only HTTP only. No credentials, no POST, no order path. GET with `timeout=20` via `httpx`, mirroring `autonomy/sports/espn.py`.
- Every network call goes through an injectable `fetch_*` callable defaulting to the real fetcher; all parser tests are hermetic (fixture dict in, dataclass out) and hit no network.
- New code lives in `autonomy/sports/statsapi.py`; tests in `tests/test_autonomy_statsapi.py`. Do not modify `espn.py`, `baseball.py`, or the forecaster in S1.
- Every `MlbGameContext` field is nullable; a missing field is recorded in `fields_present` (never fabricated). Point-in-time only: a parser never reads a field that would not exist at the snapshot time it claims.
- Run the full suite with `python -m pytest -q` before the final commit; it must stay green (baseline 4,645 passed, 0 skipped).
- Commit after every task with a `feat:`/`test:` message ending in the repo's `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: `MlbGameContext` dataclass and provenance

**Files:**
- Create: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Produces: `MlbGameContext` frozen dataclass; `SnapshotKind` = `Literal["projected","confirmed"]`; `MlbGameContext.field_provenance() -> dict[str,bool]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py
from __future__ import annotations

from autonomy.sports.statsapi import MlbGameContext


def test_context_provenance_marks_present_and_missing_fields():
    ctx = MlbGameContext(
        game_pk=717465,
        snapshot="projected",
        captured_at="2026-07-11T22:05:00+00:00",
        home="LAD",
        away="SF",
        venue="Dodger Stadium",
        home_probable_pitcher_id=477132,
        away_probable_pitcher_id=None,
        wind_speed_mph=8.0,
        wind_direction="Out To CF",
        temperature_f=74.0,
    )
    prov = ctx.field_provenance()
    assert prov["home_probable_pitcher_id"] is True
    assert prov["away_probable_pitcher_id"] is False
    assert prov["wind_direction"] is True
    # A field never set is reported absent, never invented.
    assert prov["home_lineup"] is False
    assert ctx.home_lineup == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py::test_context_provenance_marks_present_and_missing_fields -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autonomy.sports.statsapi'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py
"""Official MLB StatsAPI adapter (statsapi.mlb.com; no key). Read-only.

Produces a point-in-time MlbGameContext with confirmed lineups, platoon
splits, bullpen fatigue, park factors, pitcher rate stats, and wind/temp.
Every field is nullable and its presence is tracked, so downstream model
heads degrade gracefully and the validation harness can attribute misses to
missing inputs. Nothing here forecasts, trades, or touches credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Literal

SnapshotKind = Literal["projected", "confirmed"]


@dataclass(frozen=True)
class LineupSlot:
    batting_order: int
    player_id: int
    name: str | None = None
    bats: str | None = None  # "L" | "R" | "S"


@dataclass(frozen=True)
class PitcherRates:
    player_id: int
    name: str | None = None
    throws: str | None = None  # "L" | "R"
    era: float | None = None
    k_pct: float | None = None
    bb_pct: float | None = None
    hr9: float | None = None


@dataclass(frozen=True)
class MlbGameContext:
    game_pk: int
    snapshot: SnapshotKind
    captured_at: str  # ISO-8601 UTC receipt time (provenance)
    home: str
    away: str
    venue: str | None = None
    home_probable_pitcher_id: int | None = None
    away_probable_pitcher_id: int | None = None
    home_pitcher: PitcherRates | None = None
    away_pitcher: PitcherRates | None = None
    home_lineup: tuple[LineupSlot, ...] = ()
    away_lineup: tuple[LineupSlot, ...] = ()
    home_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    away_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    park_run_factor: float | None = None
    park_hr_factor: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    temperature_f: float | None = None

    def field_provenance(self) -> dict[str, bool]:
        """Presence map: True when a field carries real data, False when absent."""
        present: dict[str, bool] = {}
        for f in fields(self):
            if f.name in {"game_pk", "snapshot", "captured_at", "home", "away"}:
                continue
            value = getattr(self, f.name)
            present[f.name] = bool(value) if value is not None else False
        return present
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py::test_context_provenance_marks_present_and_missing_fields -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): MlbGameContext point-in-time dataclass with provenance"
```

---

### Task 2: Parse the schedule payload (probable pitchers, venue, weather)

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: `MlbGameContext`, `LineupSlot`, `PitcherRates` from Task 1.
- Produces: `parse_schedule(payload: dict, *, captured_at: str, snapshot: SnapshotKind = "projected") -> list[MlbGameContext]`.

Notes: The StatsAPI schedule endpoint is
`GET /api/v1/schedule?sportId=1&date=YYYY-MM-DD&hydrate=probablePitcher,weather,venue`.
Each `dates[].games[]` has `gamePk`, `teams.home/away.team.abbreviation`,
`teams.home/away.probablePitcher.id`, `venue.name`, and (when posted) a
`weather` block `{condition, temp, wind}` where `wind` is a string like
`"8 mph, Out To CF"`. Parse defensively — every field may be absent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import parse_schedule


_SCHEDULE_FIXTURE = {
    "dates": [
        {
            "date": "2026-07-11",
            "games": [
                {
                    "gamePk": 717465,
                    "teams": {
                        "home": {"team": {"abbreviation": "LAD"},
                                  "probablePitcher": {"id": 477132, "fullName": "C. Kershaw"}},
                        "away": {"team": {"abbreviation": "SF"},
                                  "probablePitcher": {"id": 592789, "fullName": "L. Webb"}},
                    },
                    "venue": {"name": "Dodger Stadium"},
                    "weather": {"condition": "Clear", "temp": "74", "wind": "8 mph, Out To CF"},
                },
                {
                    "gamePk": 717466,
                    "teams": {
                        "home": {"team": {"abbreviation": "NYY"}},
                        "away": {"team": {"abbreviation": "BOS"}},
                    },
                },
            ],
        }
    ]
}


def test_parse_schedule_extracts_probables_venue_weather():
    games = parse_schedule(_SCHEDULE_FIXTURE, captured_at="2026-07-11T18:00:00+00:00")
    assert len(games) == 2
    lad = next(g for g in games if g.game_pk == 717465)
    assert (lad.home, lad.away) == ("LAD", "SF")
    assert lad.snapshot == "projected"
    assert lad.home_probable_pitcher_id == 477132
    assert lad.away_probable_pitcher_id == 592789
    assert lad.venue == "Dodger Stadium"
    assert lad.temperature_f == 74.0
    assert lad.wind_speed_mph == 8.0
    assert lad.wind_direction == "Out To CF"


def test_parse_schedule_tolerates_missing_blocks():
    games = parse_schedule(_SCHEDULE_FIXTURE, captured_at="2026-07-11T18:00:00+00:00")
    nyy = next(g for g in games if g.game_pk == 717466)
    assert nyy.home_probable_pitcher_id is None
    assert nyy.venue is None
    assert nyy.temperature_f is None
    assert nyy.field_provenance()["temperature_f"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k parse_schedule -v`
Expected: FAIL with `ImportError: cannot import name 'parse_schedule'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append)


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_wind(wind: Any) -> tuple[float | None, str | None]:
    """StatsAPI wind is a string like '8 mph, Out To CF' or '' — split it."""
    if not isinstance(wind, str) or not wind.strip():
        return None, None
    speed: float | None = None
    direction: str | None = None
    parts = [p.strip() for p in wind.split(",", 1)]
    head = parts[0]
    if "mph" in head:
        speed = _float(head.replace("mph", "").strip())
        direction = parts[1] if len(parts) > 1 else None
    else:
        direction = wind.strip()
    return speed, (direction or None)


def parse_schedule(
    payload: dict[str, Any],
    *,
    captured_at: str,
    snapshot: SnapshotKind = "projected",
) -> list[MlbGameContext]:
    """Point-in-time contexts from the hydrated schedule endpoint."""
    contexts: list[MlbGameContext] = []
    for date_block in payload.get("dates", []) or []:
        for game in date_block.get("games", []) or []:
            teams = game.get("teams", {}) or {}
            home = ((teams.get("home", {}) or {}).get("team", {}) or {}).get("abbreviation")
            away = ((teams.get("away", {}) or {}).get("team", {}) or {}).get("abbreviation")
            game_pk = game.get("gamePk")
            if not home or not away or game_pk is None:
                continue
            home_prob = ((teams.get("home", {}) or {}).get("probablePitcher", {}) or {}).get("id")
            away_prob = ((teams.get("away", {}) or {}).get("probablePitcher", {}) or {}).get("id")
            weather = game.get("weather", {}) or {}
            wind_speed, wind_direction = _parse_wind(weather.get("wind"))
            contexts.append(MlbGameContext(
                game_pk=int(game_pk),
                snapshot=snapshot,
                captured_at=captured_at,
                home=str(home),
                away=str(away),
                venue=((game.get("venue", {}) or {}).get("name")),
                home_probable_pitcher_id=int(home_prob) if home_prob is not None else None,
                away_probable_pitcher_id=int(away_prob) if away_prob is not None else None,
                wind_speed_mph=wind_speed,
                wind_direction=wind_direction,
                temperature_f=_float(weather.get("temp")),
            ))
    return contexts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k parse_schedule -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): parse StatsAPI schedule into projected contexts"
```

---

### Task 3: Parse confirmed lineups + handedness from the boxscore

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: `MlbGameContext`, `LineupSlot` from Task 1.
- Produces: `parse_boxscore_lineups(boxscore: dict, roster_bats: dict[int,str] | None = None) -> tuple[tuple[LineupSlot,...], tuple[LineupSlot,...]]` returning `(home_lineup, away_lineup)` ordered by batting order; `apply_confirmed_lineups(ctx, home_lineup, away_lineup) -> MlbGameContext` producing a `snapshot="confirmed"` copy.

Notes: boxscore is `GET /api/v1/game/{gamePk}/boxscore`; `teams.home/away.battingOrder` is a list of player ids (length 9 when posted) and `teams.home/away.players["ID{id}"]` carries `person.fullName` and `person.batSide.code`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from dataclasses import replace as _replace

from autonomy.sports.statsapi import (
    apply_confirmed_lineups, parse_boxscore_lineups,
)

_BOX_FIXTURE = {
    "teams": {
        "home": {
            "battingOrder": [605141, 518692],
            "players": {
                "ID605141": {"person": {"fullName": "M. Betts", "batSide": {"code": "R"}}},
                "ID518692": {"person": {"fullName": "F. Freeman", "batSide": {"code": "L"}}},
            },
        },
        "away": {
            "battingOrder": [592885],
            "players": {
                "ID592885": {"person": {"fullName": "T. Estrada", "batSide": {"code": "R"}}},
            },
        },
    }
}


def test_parse_boxscore_lineups_orders_and_reads_handedness():
    home, away = parse_boxscore_lineups(_BOX_FIXTURE)
    assert [s.player_id for s in home] == [605141, 518692]
    assert home[0].batting_order == 1 and home[0].bats == "R"
    assert home[1].name == "F. Freeman" and home[1].bats == "L"
    assert [s.player_id for s in away] == [592885]


def test_apply_confirmed_lineups_promotes_snapshot():
    base = MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="LAD", away="SF",
    )
    home, away = parse_boxscore_lineups(_BOX_FIXTURE)
    confirmed = apply_confirmed_lineups(
        base, home, away, captured_at="2026-07-11T22:40:00+00:00",
    )
    assert confirmed.snapshot == "confirmed"
    assert confirmed.captured_at == "2026-07-11T22:40:00+00:00"
    assert len(confirmed.home_lineup) == 2
    assert base.home_lineup == ()  # original untouched (frozen dataclass)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k "lineup" -v`
Expected: FAIL with `ImportError: cannot import name 'parse_boxscore_lineups'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append)
from dataclasses import replace


def _team_lineup(team_box: dict[str, Any]) -> tuple[LineupSlot, ...]:
    order = team_box.get("battingOrder") or []
    players = team_box.get("players", {}) or {}
    slots: list[LineupSlot] = []
    for index, player_id in enumerate(order, start=1):
        person = (players.get(f"ID{player_id}", {}) or {}).get("person", {}) or {}
        slots.append(LineupSlot(
            batting_order=index,
            player_id=int(player_id),
            name=person.get("fullName"),
            bats=((person.get("batSide", {}) or {}).get("code")),
        ))
    return tuple(slots)


def parse_boxscore_lineups(
    boxscore: dict[str, Any], roster_bats: dict[int, str] | None = None,
) -> tuple[tuple[LineupSlot, ...], tuple[LineupSlot, ...]]:
    teams = boxscore.get("teams", {}) or {}
    home = _team_lineup(teams.get("home", {}) or {})
    away = _team_lineup(teams.get("away", {}) or {})
    return home, away


def apply_confirmed_lineups(
    ctx: MlbGameContext,
    home_lineup: tuple[LineupSlot, ...],
    away_lineup: tuple[LineupSlot, ...],
    *,
    captured_at: str,
) -> MlbGameContext:
    """Return a confirmed-snapshot copy carrying the real lineups."""
    return replace(
        ctx,
        snapshot="confirmed",
        captured_at=captured_at,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k "lineup" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): parse confirmed lineups + handedness, two-snapshot promotion"
```

---

### Task 4: Parse pitcher season rate stats

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: `PitcherRates` from Task 1.
- Produces: `parse_pitcher_rates(people_payload: dict) -> PitcherRates | None`.

Notes: endpoint is `GET /api/v1/people/{id}?hydrate=stats(group=[pitching],type=[season])`;
`people[0]` carries `id`, `fullName`, `pitchHand.code`, and
`stats[0].splits[0].stat` with `era`, `strikeOuts`, `baseOnBalls`,
`battersFaced`, `homeRunsPer9` (or compute from `homeRuns`/`inningsPitched`).
K% = strikeOuts / battersFaced; BB% = baseOnBalls / battersFaced.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import parse_pitcher_rates

_PEOPLE_FIXTURE = {
    "people": [
        {
            "id": 592789,
            "fullName": "L. Webb",
            "pitchHand": {"code": "R"},
            "stats": [
                {"splits": [{"stat": {
                    "era": "3.25",
                    "strikeOuts": 150,
                    "baseOnBalls": 40,
                    "battersFaced": 750,
                    "homeRunsPer9": "0.85",
                }}]}
            ],
        }
    ]
}


def test_parse_pitcher_rates_computes_k_and_bb_pct():
    rates = parse_pitcher_rates(_PEOPLE_FIXTURE)
    assert rates.player_id == 592789
    assert rates.throws == "R"
    assert rates.era == 3.25
    assert rates.k_pct == round(150 / 750, 4)
    assert rates.bb_pct == round(40 / 750, 4)
    assert rates.hr9 == 0.85


def test_parse_pitcher_rates_returns_none_on_empty():
    assert parse_pitcher_rates({"people": []}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k pitcher_rates -v`
Expected: FAIL with `ImportError: cannot import name 'parse_pitcher_rates'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append)


def _rate(numerator: Any, denominator: Any) -> float | None:
    n, d = _float(numerator), _float(denominator)
    if n is None or not d:
        return None
    return round(n / d, 4)


def parse_pitcher_rates(people_payload: dict[str, Any]) -> PitcherRates | None:
    people = people_payload.get("people") or []
    if not people:
        return None
    person = people[0] or {}
    pid = person.get("id")
    if pid is None:
        return None
    stat: dict[str, Any] = {}
    stats = person.get("stats") or []
    if stats:
        splits = (stats[0] or {}).get("splits") or []
        if splits:
            stat = (splits[0] or {}).get("stat", {}) or {}
    return PitcherRates(
        player_id=int(pid),
        name=person.get("fullName"),
        throws=((person.get("pitchHand", {}) or {}).get("code")),
        era=_float(stat.get("era")),
        k_pct=_rate(stat.get("strikeOuts"), stat.get("battersFaced")),
        bb_pct=_rate(stat.get("baseOnBalls"), stat.get("battersFaced")),
        hr9=_float(stat.get("homeRunsPer9")),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k pitcher_rates -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): parse pitcher season rate stats (K%, BB%, HR/9)"
```

---

### Task 5: Static park factors and bullpen-fatigue derivation

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Produces: `PARK_FACTORS: dict[str, tuple[float, float]]` (venue -> (run_factor, hr_factor)); `park_factors(venue: str | None) -> tuple[float | None, float | None]`; `bullpen_fatigue(recent_appearances: dict[int, list[str]], as_of: str) -> dict[int, float]` where a reliever's fatigue in [0,1] rises with appearances in the trailing 3 days.

Notes: park factors are a small static table seeded from public league-average
run/HR indices (neutral = 1.0); refined later by the feature-discovery loop.
Bullpen fatigue is derived from the trailing-3-day appearance dates already
available via the schedule, not a new endpoint.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import bullpen_fatigue, park_factors


def test_park_factors_known_and_neutral():
    run, hr = park_factors("Coors Field")
    assert run > 1.0 and hr > 1.0  # hitter park
    assert park_factors("Unknown Yard") == (1.0, 1.0)
    assert park_factors(None) == (None, None)


def test_bullpen_fatigue_rises_with_recent_use():
    recent = {
        101: ["2026-07-10", "2026-07-09", "2026-07-08"],  # 3 straight days
        102: ["2026-07-06"],                                # rested
        103: [],
    }
    fatigue = bullpen_fatigue(recent, as_of="2026-07-11")
    assert fatigue[101] > fatigue[102] > 0.0
    assert fatigue[103] == 0.0
    assert 0.0 <= fatigue[101] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k "park or fatigue" -v`
Expected: FAIL with `ImportError: cannot import name 'park_factors'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append)
from datetime import date


# Seed table from public league-average park indices; neutral = 1.0. The
# feature-discovery loop (S5) refines these from residuals later.
PARK_FACTORS: dict[str, tuple[float, float]] = {
    "Coors Field": (1.15, 1.18),
    "Fenway Park": (1.05, 1.03),
    "Dodger Stadium": (0.98, 1.06),
    "Oracle Park": (0.94, 0.90),
    "Great American Ball Park": (1.03, 1.16),
    "Petco Park": (0.96, 0.95),
    "Yankee Stadium": (1.01, 1.10),
}


def park_factors(venue: str | None) -> tuple[float | None, float | None]:
    if venue is None:
        return None, None
    return PARK_FACTORS.get(venue, (1.0, 1.0))


def bullpen_fatigue(
    recent_appearances: dict[int, list[str]], *, as_of: str,
) -> dict[int, float]:
    """Fatigue in [0,1]: weighted count of appearances in the trailing 3 days.

    Yesterday weighs most (back-to-back), then two- and three-days-ago. The
    weights sum to 1.0 so a reliever who pitched all three trailing days
    saturates at 1.0.
    """
    reference = date.fromisoformat(as_of)
    day_weight = {1: 0.5, 2: 0.3, 3: 0.2}
    fatigue: dict[int, float] = {}
    for player_id, dates in recent_appearances.items():
        score = 0.0
        for stamp in dates:
            try:
                delta = (reference - date.fromisoformat(stamp)).days
            except ValueError:
                continue
            score += day_weight.get(delta, 0.0)
        fatigue[int(player_id)] = round(min(1.0, score), 4)
    return fatigue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k "park or fatigue" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): static park factors + trailing-3-day bullpen fatigue"
```

---

### Task 6: `StatsApiClient` — injectable fetchers, cache, context assembly

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: all parsers from Tasks 2-5.
- Produces: `default_fetch_schedule`, `default_fetch_boxscore`, `default_fetch_people` (real `httpx` GETs); `StatsApiClient(fetch_schedule=None, fetch_boxscore=None, fetch_people=None)` with `projected_contexts(date_iso, *, captured_at) -> list[MlbGameContext]` (schedule + pitcher rates hydrated) and `confirm_lineups(ctx, *, captured_at) -> MlbGameContext` (boxscore promotion). Fetchers are injected in tests; nothing hits the network.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import StatsApiClient


def test_client_assembles_projected_context_with_pitcher_rates():
    def fake_schedule(date_iso):
        assert date_iso == "2026-07-11"
        return _SCHEDULE_FIXTURE

    def fake_people(player_id):
        assert player_id in {477132, 592789}
        return _PEOPLE_FIXTURE

    client = StatsApiClient(
        fetch_schedule=fake_schedule, fetch_people=fake_people,
    )
    contexts = client.projected_contexts(
        "2026-07-11", captured_at="2026-07-11T18:00:00+00:00",
    )
    lad = next(c for c in contexts if c.game_pk == 717465)
    assert lad.snapshot == "projected"
    assert lad.away_pitcher is not None
    assert lad.away_pitcher.k_pct == round(150 / 750, 4)
    assert lad.park_run_factor == 0.98  # Dodger Stadium from the table


def test_client_confirms_lineups_via_boxscore():
    client = StatsApiClient(fetch_boxscore=lambda pk: _BOX_FIXTURE)
    base = MlbGameContext(
        game_pk=717465, snapshot="projected",
        captured_at="2026-07-11T18:00:00+00:00", home="LAD", away="SF",
    )
    confirmed = client.confirm_lineups(base, captured_at="2026-07-11T22:40:00+00:00")
    assert confirmed.snapshot == "confirmed"
    assert len(confirmed.home_lineup) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k client -v`
Expected: FAIL with `ImportError: cannot import name 'StatsApiClient'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append)
from typing import Callable

_BASE = "https://statsapi.mlb.com/api/v1"


def default_fetch_schedule(date_iso: str) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/schedule",
        params={
            "sportId": 1, "date": date_iso,
            "hydrate": "probablePitcher,weather,venue",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def default_fetch_boxscore(game_pk: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(f"{_BASE}/game/{game_pk}/boxscore", timeout=20)
    response.raise_for_status()
    return response.json()


def default_fetch_people(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[pitching],type=[season])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


class StatsApiClient:
    """Assembles point-in-time MlbGameContexts from injectable StatsAPI fetchers."""

    def __init__(
        self,
        fetch_schedule: Callable[[str], dict[str, Any]] | None = None,
        fetch_boxscore: Callable[[int], dict[str, Any]] | None = None,
        fetch_people: Callable[[int], dict[str, Any]] | None = None,
    ) -> None:
        self.fetch_schedule = fetch_schedule or default_fetch_schedule
        self.fetch_boxscore = fetch_boxscore or default_fetch_boxscore
        self.fetch_people = fetch_people or default_fetch_people
        self._pitcher_cache: dict[int, PitcherRates | None] = {}

    def _pitcher(self, player_id: int | None) -> PitcherRates | None:
        if player_id is None:
            return None
        if player_id not in self._pitcher_cache:
            try:
                self._pitcher_cache[player_id] = parse_pitcher_rates(
                    self.fetch_people(player_id)
                )
            except Exception:
                self._pitcher_cache[player_id] = None
        return self._pitcher_cache[player_id]

    def projected_contexts(
        self, date_iso: str, *, captured_at: str,
    ) -> list[MlbGameContext]:
        contexts = parse_schedule(
            self.fetch_schedule(date_iso), captured_at=captured_at,
        )
        hydrated: list[MlbGameContext] = []
        for ctx in contexts:
            run_factor, hr_factor = park_factors(ctx.venue)
            hydrated.append(replace(
                ctx,
                home_pitcher=self._pitcher(ctx.home_probable_pitcher_id),
                away_pitcher=self._pitcher(ctx.away_probable_pitcher_id),
                park_run_factor=run_factor,
                park_hr_factor=hr_factor,
            ))
        return hydrated

    def confirm_lineups(
        self, ctx: MlbGameContext, *, captured_at: str,
    ) -> MlbGameContext:
        home, away = parse_boxscore_lineups(self.fetch_boxscore(ctx.game_pk))
        return apply_confirmed_lineups(ctx, home, away, captured_at=captured_at)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k client -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full new test module and commit**

Run: `python -m pytest tests/test_autonomy_statsapi.py -v`
Expected: all tests PASS.

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): StatsApiClient assembles two-snapshot contexts"
```

---

### Task 7: Live verification against tonight's real slate + reconcile parser

**Files:**
- Create: `scripts/verify_statsapi_live.py`
- Modify: `autonomy/sports/statsapi.py` (only if the live JSON reveals a field-path mismatch)

**Interfaces:**
- Consumes: `StatsApiClient` from Task 6.

Notes: this task hits the real, public StatsAPI once to prove the parsers
match live JSON. It is a script, not a unit test (unit tests stay hermetic).
If the live payload differs from the fixtures (StatsAPI field paths can shift),
adjust the parser and re-run the hermetic suite to confirm no regression.

- [ ] **Step 1: Write the live verification script**

```python
# scripts/verify_statsapi_live.py
"""One-shot live check of the MLB StatsAPI parsers against a real slate.

Read-only, keyless. Prints how many of tonight's games populated each field
so a human can confirm the foundation works end-to-end before model heads
consume it. Not part of the hermetic test suite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from autonomy.sports.statsapi import StatsApiClient


def main() -> int:
    date_iso = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    client = StatsApiClient()
    contexts = client.projected_contexts(date_iso, captured_at=now)
    if not contexts:
        print(f"No MLB games found for {date_iso}")
        return 0
    fields_seen = {k: 0 for k in contexts[0].field_provenance()}
    for ctx in contexts:
        for field_name, present in ctx.field_provenance().items():
            fields_seen[field_name] += int(present)
    total = len(contexts)
    print(f"{date_iso}: {total} games")
    for field_name, count in sorted(fields_seen.items(), key=lambda kv: -kv[1]):
        print(f"  {field_name:28} {count}/{total}")
    # Prove a confirmed-lineup promotion works on the first game with a boxscore.
    sample = contexts[0]
    confirmed = client.confirm_lineups(sample, captured_at=now)
    print(
        f"confirm_lineups({sample.game_pk}): "
        f"home {len(confirmed.home_lineup)} / away {len(confirmed.away_lineup)} batters"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it against the real slate**

Run: `python scripts/verify_statsapi_live.py`
Expected: prints tonight's game count and a per-field population table; probable
pitchers, venue, and park factors should populate for most games; lineups
populate only for games inside their pre-game window. If any parser raised or a
field the payload clearly contains reads 0/total, the live JSON path differs.

- [ ] **Step 3: Reconcile the parser if needed**

If a field mismatch surfaced, adjust the corresponding `parse_*` in
`autonomy/sports/statsapi.py` to the real path, then re-run the hermetic module:

Run: `python -m pytest tests/test_autonomy_statsapi.py -v`
Expected: all PASS (fixtures updated to match the corrected path if they moved).

- [ ] **Step 4: Run the full suite for regression**

Run: `python -m pytest -q`
Expected: full suite green (>= 4,645 passed, 0 skipped; new statsapi tests added).

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_statsapi_live.py autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): live StatsAPI verification script + parser reconciliation"
```

---

## Self-Review

**Spec coverage (S1 scope only):**
- Keyless StatsAPI ingestion — Tasks 2-6 (schedule, boxscore, people) ✓
- Confirmed lineups + handedness — Task 3 ✓
- Platoon splits — batter `bats` + pitcher `throws` captured (Tasks 3-4); the platoon *computation* is an engine concern (S3), correctly out of S1 scope ✓
- Bullpen fatigue — Task 5 ✓
- True park factors — Task 5 (seed table; S5 refines) ✓
- Per-pitcher rates (K%/BB%/HR9) — Task 4 ✓
- Wind + temperature — Task 2 ✓
- Two-snapshot projected/confirmed with provenance — Tasks 1, 3, 6 ✓
- Point-in-time / lookahead-free — `captured_at` on every context; live verify Task 7 ✓
- ESPN fallback untouched — no edit to `espn.py` in any task ✓

**Placeholder scan:** none — every step carries runnable test and implementation code.

**Type consistency:** `MlbGameContext`, `LineupSlot`, `PitcherRates`, `SnapshotKind`, `parse_schedule`, `parse_boxscore_lineups`, `apply_confirmed_lineups`, `parse_pitcher_rates`, `park_factors`, `bullpen_fatigue`, `StatsApiClient.projected_contexts`, `StatsApiClient.confirm_lineups` are used with consistent names/signatures across tasks. `replace` imported once (Task 3) and reused (Task 6) — same module, no redefinition.

**Out of S1 scope (correctly deferred):** model heads (S3-S4), validation harness (S2), signal registration + forecaster wiring, scheduler cadence integration, recursive loops (S5).
