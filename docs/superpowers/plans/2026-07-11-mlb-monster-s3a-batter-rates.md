# MLB Monster S3a — Per-Batter Offensive Rates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the S1 StatsAPI data layer with per-batter season offensive rates (K%, BB%, OBP, SLG, ISO), hydrated onto the confirmed lineup, so the S3b plate-appearance simulator can weigh a real lineup's quality — the payoff of capturing confirmed lineups and the two-snapshot lineup-delta edge.

**Architecture:** Append to the existing `autonomy/sports/statsapi.py`: a `BatterRates` dataclass, a `parse_batter_rates` pure parser over the StatsAPI `people` hitting-stats payload, a keyless `default_fetch_batter_people` fetcher, and a `StatsApiClient.hydrate_batter_rates(ctx)` method that fetches rates for every lineup `player_id` and attaches them to a new `batter_rates` map on `MlbGameContext`. Mirrors the existing pitcher-rate path exactly (injectable fetcher, per-id cache). No simulator yet (that is S3b); no live production wiring (governance-gated).

**Tech Stack:** Python 3.11+, `httpx` (existing dep), `pytest`. Endpoint `GET /api/v1/people/{id}?hydrate=stats(group=[hitting],type=[season])` (no key).

## Global Constraints

- Python `>=3.11`; the module already has `from __future__ import annotations`.
- Append only to `autonomy/sports/statsapi.py`; tests in `tests/test_autonomy_statsapi.py`; the live check extends `scripts/verify_statsapi_live.py`. Do not modify any other file.
- Keyless, read-only HTTP via an injectable fetcher defaulting to the real one; all parser tests hermetic (fixture in, dataclass out), no network. Mirror the existing `default_fetch_people` / `_pitcher` / `parse_pitcher_rates` idiom exactly (httpx GET, `timeout=20`, `.raise_for_status()`).
- Every rate field nullable; a missing stat yields `None`, never fabricated; a zero/missing denominator yields `None` for that rate (no `ZeroDivisionError`). Reuse the module's existing `_float` and `_rate` helpers — do not re-implement them.
- `hydrate_batter_rates` must not raise if a single batter fetch fails — swallow to a missing entry (like `_pitcher`), so one bad lookup cannot crash context assembly.
- `MlbGameContext` stays frozen; the new `batter_rates` field uses `field(default_factory=dict)`; `hydrate_batter_rates` returns a new context via `dataclasses.replace` (never mutates the input).
- Run the full suite with `python -m pytest -q` before the final commit; it must stay green (baseline after S2 merge: 4,682 passed, 0 skipped).
- Commit after every task with a `feat:`/`test:` message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: `BatterRates` dataclass + `batter_rates` context field

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Produces: `BatterRates` frozen dataclass (`player_id: int`, `name: str | None`, `bats: str | None`, `plate_appearances: int | None`, `k_pct: float | None`, `bb_pct: float | None`, `obp: float | None`, `slg: float | None`, `iso: float | None`); a new field `batter_rates: dict[int, BatterRates] = field(default_factory=dict)` on `MlbGameContext`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import BatterRates


def test_batter_rates_attaches_to_context_and_reports_provenance():
    from autonomy.sports.statsapi import MlbGameContext
    rates = BatterRates(
        player_id=605141, name="M. Betts", bats="R",
        plate_appearances=600, k_pct=0.16, bb_pct=0.10,
        obp=0.36, slg=0.52, iso=0.24,
    )
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="LAD", away="SF", batter_rates={605141: rates},
    )
    assert ctx.batter_rates[605141].obp == 0.36
    assert ctx.field_provenance()["batter_rates"] is True
    # Absent by default (empty map) -> reported absent.
    empty = MlbGameContext(
        game_pk=2, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="NYY", away="BOS",
    )
    assert empty.field_provenance()["batter_rates"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k batter_rates_attaches -v`
Expected: FAIL with `ImportError: cannot import name 'BatterRates'`.

- [ ] **Step 3: Write minimal implementation**

Add the dataclass next to `PitcherRates`:

```python
# autonomy/sports/statsapi.py (add near PitcherRates)
@dataclass(frozen=True)
class BatterRates:
    player_id: int
    name: str | None = None
    bats: str | None = None  # "L" | "R" | "S"
    plate_appearances: int | None = None
    k_pct: float | None = None
    bb_pct: float | None = None
    obp: float | None = None
    slg: float | None = None
    iso: float | None = None
```

Add the field to `MlbGameContext` (after `away_bullpen_fatigue`, keeping all defaulted fields together):

```python
    batter_rates: dict[int, BatterRates] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k batter_rates_attaches -v`
Expected: PASS.

- [ ] **Step 5: Run the full statsapi module to confirm no S1 regression, then commit**

Run: `python -m pytest tests/test_autonomy_statsapi.py -q`
Expected: all existing S1 tests still pass (the new field defaults empty; provenance keys are checked individually, not as an exhaustive set).

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): BatterRates dataclass + batter_rates context field"
```

---

### Task 2: `parse_batter_rates` — hitting-stats parser

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: `BatterRates` (Task 1); the module's existing `_float` and `_rate` helpers.
- Produces: `parse_batter_rates(people_payload: dict) -> BatterRates | None`.

Notes: endpoint payload is `people[0]` with `id`, `fullName`, `batSide.code`, and `stats[0].splits[0].stat` carrying `plateAppearances`, `strikeOuts`, `baseOnBalls`, `obp`, `slg` (strings or numbers). K% = strikeOuts / plateAppearances; BB% = baseOnBalls / plateAppearances; ISO = slg - avg IF both present, else `slg - (obp-derived)` is unreliable, so compute `iso = slg - battingAverage` when `stat` has `avg`, else leave `None`. Return `None` when `people` is empty or the id is absent. Reuse `_rate(numerator, denominator)` for K%/BB% and `_float` for obp/slg/avg.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
from autonomy.sports.statsapi import parse_batter_rates

_BATTER_FIXTURE = {
    "people": [
        {
            "id": 605141,
            "fullName": "M. Betts",
            "batSide": {"code": "R"},
            "stats": [
                {"splits": [{"stat": {
                    "plateAppearances": 600,
                    "strikeOuts": 90,
                    "baseOnBalls": 60,
                    "obp": "0.360",
                    "slg": "0.520",
                    "avg": "0.280",
                }}]}
            ],
        }
    ]
}


def test_parse_batter_rates_computes_rates_and_iso():
    rates = parse_batter_rates(_BATTER_FIXTURE)
    assert rates.player_id == 605141
    assert rates.bats == "R"
    assert rates.plate_appearances == 600
    assert rates.k_pct == round(90 / 600, 4)
    assert rates.bb_pct == round(60 / 600, 4)
    assert rates.obp == 0.360
    assert rates.slg == 0.520
    assert rates.iso == round(0.520 - 0.280, 4)  # slg - avg


def test_parse_batter_rates_none_on_empty_and_missing_denominator():
    assert parse_batter_rates({"people": []}) is None
    zero = {"people": [{"id": 7, "stats": [{"splits": [{"stat": {
        "plateAppearances": 0, "strikeOuts": 3, "baseOnBalls": 1, "slg": "0.400",
    }}]}]}]}
    rates = parse_batter_rates(zero)
    assert rates.player_id == 7
    assert rates.k_pct is None and rates.bb_pct is None  # no divide-by-zero
    assert rates.iso is None  # no avg -> ISO unknown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k parse_batter_rates -v`
Expected: FAIL with `ImportError: cannot import name 'parse_batter_rates'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/statsapi.py (append, after parse_pitcher_rates)
def parse_batter_rates(people_payload: dict[str, Any]) -> BatterRates | None:
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
    pa = stat.get("plateAppearances")
    slg = _float(stat.get("slg"))
    avg = _float(stat.get("avg"))
    iso = round(slg - avg, 4) if slg is not None and avg is not None else None
    return BatterRates(
        player_id=int(pid),
        name=person.get("fullName"),
        bats=((person.get("batSide", {}) or {}).get("code")),
        plate_appearances=int(pa) if pa is not None else None,
        k_pct=_rate(stat.get("strikeOuts"), pa),
        bb_pct=_rate(stat.get("baseOnBalls"), pa),
        obp=_float(stat.get("obp")),
        slg=slg,
        iso=iso,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k parse_batter_rates -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): parse batter season rates (K%, BB%, OBP, SLG, ISO)"
```

---

### Task 3: batter fetcher + `StatsApiClient.hydrate_batter_rates`

**Files:**
- Modify: `autonomy/sports/statsapi.py`
- Test: `tests/test_autonomy_statsapi.py`

**Interfaces:**
- Consumes: `parse_batter_rates` (Task 2); `MlbGameContext`, `LineupSlot`, `replace`.
- Produces: `default_fetch_batter_people(player_id) -> dict` (real httpx GET with `group=[hitting]`); `StatsApiClient.__init__` gains a `fetch_batter_people` param (defaulting to the real fetcher) and a `_batter_cache`; `StatsApiClient.hydrate_batter_rates(ctx) -> MlbGameContext` fetches rates for every `player_id` in `ctx.home_lineup + ctx.away_lineup`, swallowing individual failures, and returns a context with the `batter_rates` map populated. `clear_cache()` also clears the batter cache.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_statsapi.py (append)
def test_client_hydrate_batter_rates_fills_lineup_and_swallows_failures():
    from autonomy.sports.statsapi import StatsApiClient, MlbGameContext, LineupSlot

    def fake_batter(player_id):
        if player_id == 999:
            raise RuntimeError("statsapi down")
        return {"people": [{"id": player_id, "fullName": f"P{player_id}",
                            "batSide": {"code": "L"}, "stats": [{"splits": [{"stat": {
                                "plateAppearances": 500, "strikeOuts": 100,
                                "baseOnBalls": 50, "obp": "0.340", "slg": "0.450",
                                "avg": "0.270"}}]}]}]}

    client = StatsApiClient(fetch_batter_people=fake_batter)
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="LAD", away="SF",
        home_lineup=(LineupSlot(1, 605141), LineupSlot(2, 999)),
        away_lineup=(LineupSlot(1, 592885),),
    )
    hydrated = client.hydrate_batter_rates(ctx)
    assert set(hydrated.batter_rates) == {605141, 592885}  # 999 failed -> absent
    assert hydrated.batter_rates[605141].k_pct == round(100 / 500, 4)
    assert ctx.batter_rates == {}  # original untouched (frozen)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k hydrate_batter_rates -v`
Expected: FAIL with `TypeError` (unexpected `fetch_batter_people`) or `AttributeError` (`hydrate_batter_rates`).

- [ ] **Step 3: Write minimal implementation**

Add the fetcher next to `default_fetch_people`:

```python
def default_fetch_batter_people(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[hitting],type=[season])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
```

Extend `StatsApiClient.__init__` (add the param + cache), `clear_cache`, and add the method:

```python
    # in __init__ signature, add:  fetch_batter_people: Callable[[int], dict[str, Any]] | None = None,
    # in __init__ body, add:
        self.fetch_batter_people = fetch_batter_people or default_fetch_batter_people
        self._batter_cache: dict[int, BatterRates | None] = {}

    # in clear_cache, add:
        self._batter_cache.clear()

    def _batter(self, player_id: int) -> BatterRates | None:
        if player_id not in self._batter_cache:
            try:
                self._batter_cache[player_id] = parse_batter_rates(
                    self.fetch_batter_people(player_id)
                )
            except Exception:
                self._batter_cache[player_id] = None
        return self._batter_cache[player_id]

    def hydrate_batter_rates(self, ctx: MlbGameContext) -> MlbGameContext:
        """Attach season offensive rates for every batter in both lineups."""
        rates: dict[int, BatterRates] = {}
        for slot in (*ctx.home_lineup, *ctx.away_lineup):
            batter = self._batter(slot.player_id)
            if batter is not None:
                rates[slot.player_id] = batter
        return replace(ctx, batter_rates=rates)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_statsapi.py -k hydrate_batter_rates -v`
Expected: PASS.

- [ ] **Step 5: Run the full statsapi module, then commit**

Run: `python -m pytest tests/test_autonomy_statsapi.py -q`
Expected: all PASS (S1 + S3a).

```bash
git add autonomy/sports/statsapi.py tests/test_autonomy_statsapi.py
git commit -m "feat(mlb): batter fetcher + hydrate_batter_rates on confirmed lineup"
```

---

### Task 4: live verification of batter-rate hydration

**Files:**
- Modify: `scripts/verify_statsapi_live.py`

**Interfaces:**
- Consumes: `StatsApiClient.confirm_lineups`, `StatsApiClient.hydrate_batter_rates`.

Notes: extend the existing live script (read-only, keyless). After it confirms lineups for the first game with a posted lineup, hydrate batter rates and print how many lineup batters got real rates. If lineups are not yet posted (common far before first pitch), print that clearly and skip — not a failure.

- [ ] **Step 1: Add the batter-rate probe to the script**

Add, after the existing `confirm_lineups` block in `scripts/verify_statsapi_live.py`:

```python
    confirmed = client.confirm_lineups(sample, captured_at=now)
    total_batters = len(confirmed.home_lineup) + len(confirmed.away_lineup)
    if total_batters:
        with_rates = client.hydrate_batter_rates(confirmed)
        got = len(with_rates.batter_rates)
        print(f"hydrate_batter_rates: {got}/{total_batters} lineup batters have rates")
    else:
        print("no lineups posted yet (pre-game) - batter-rate probe skipped")
```

- [ ] **Step 2: Run it against the real slate**

Run: `python scripts/verify_statsapi_live.py`
Expected: prints the schedule population table (S1) plus either a batter-rate count for a game whose lineup is posted, or the "no lineups posted yet" skip. Must not raise.

- [ ] **Step 3: Run the full suite for regression**

Run: `python -m pytest -q`
Expected: full suite green (>= 4,682 passed, 0 skipped, plus the new S3a tests).

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_statsapi_live.py
git commit -m "feat(mlb): live verification of batter-rate hydration"
```

---

## Self-Review

**Spec coverage (S3a = the batter-rate prerequisite for S3b's PA-sim):**
- Per-batter offensive rates ingested keyless — Tasks 2-3 ✓
- Rates attached to the confirmed lineup, hydrated like pitcher rates — Task 3 ✓
- K%/BB%/OBP/SLG/ISO — Task 2 ✓ (ISO only when `avg` present; documented)
- Nullable + defensive (empty people, zero denominator, fetch failure swallowed) — Tasks 2-3 ✓
- Frozen/immutable, `replace`-based hydration, provenance — Tasks 1, 3 ✓
- Live-verified — Task 4 ✓

**Placeholder scan:** none — every step carries runnable test and implementation code.

**Type consistency:** `BatterRates`, `batter_rates` field, `parse_batter_rates`, `default_fetch_batter_people`, `StatsApiClient._batter`, `StatsApiClient.hydrate_batter_rates` are used with consistent names/signatures across tasks; reuses `_float`, `_rate`, `replace`, `LineupSlot`, `MlbGameContext` from S1 without redefining.

**Out of S3a scope (S3b and beyond):** the plate-appearance simulator itself, the log5 outcome model, game/inning simulation, source registration, S2 grading of the engine, and any live production wiring (governance-gated). S3a only makes the data available.
