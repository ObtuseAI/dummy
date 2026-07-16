# Fantasy-Data Intake Layer

The fantasy layer ingests public projection / fantasy feeds as **internal
challenger evidence** and triangulates them against Dummy's own live models and
market prices. It is a multi-leg build; this document tracks each leg.

| Leg | Source | Status | Module |
| --- | --- | --- | --- |
| #1 | FanGraphs projection consensus | **shipped** | `autonomy/ingest/fantasy/fangraphs.py` |
| #2 | Player props (sportsbook prop lines) | planned | — |
| #3 | ESPN fantasy baseball (flb) | planned | — |

Legs #2 (props) and #3 (ESPN-flb) land in later waves; leg #1 is the first
fantasy-data source and the anchor the later legs triangulate against.

## Leg #1 — FanGraphs projection consensus

### Source

Keyless public projections JSON API (the same endpoint the FanGraphs
projections table calls in the browser):

```
https://www.fangraphs.com/api/projections?type=steamer&stats=bat&pos=all&team=0
https://www.fangraphs.com/api/projections?type=steamer&stats=pit&pos=all&team=0
```

- `type` (projection system): `steamer` (default), `zips`, `thebat`, `thebatx`, `atc`
- `stats`: `bat` | `pit`
- Verified keyless, returning JSON, on 2026-07-16.

**Batter** rows carry `PlayerName`, `Team`, `R`, `HR`, `RBI`, `SB`, `wOBA`,
`wRC+`, `WAR`, plus `q10..q90` wOBA-percentile bands and `ADP`.
**Pitcher** rows carry `ERA`, `FIP`, `SO`, `IP`, `WAR`, plus `q10..q90`
ERA-percentile bands and `ADP`.

Endpoint quirk: the API sits behind Cloudflare and can challenge datacenter
IPs; residential/browser reads succeed. The fetcher sends a browser
`User-Agent`, `Accept`, and `Referer` and treats any non-JSON response as a
failed fetch (empty book), never retrying in a loop.

### Terms-of-service posture

FanGraphs projections are used **strictly as internal challenger evidence**.
Nothing fetched is redistributed, republished, resold, or exposed downstream.
The reads are courteous: a browser `User-Agent`, a bounded timeout, and a single
`bat` + `pit` fetch **per cycle**. If FanGraphs indicates that automated reads
are unwelcome, this leg is retired rather than worked around. The same note is
carried in the module header so the constraint travels with the code.

### Cadence & failure posture

- **One fetch per cycle.** `ProjectionBook.refresh()` is the only network
  trigger; it is invoked once per cycle from the signal's `on_cycle_start`.
- **Season-gated.** The shared `SeasonMonitor` skips the fetch entirely when MLB
  is dormant (Nov–Feb); the book resets to empty.
- **Fail-closed.** Any fetch or parse error yields an **empty** book, which makes
  every downstream emission abstain — byte-identical to a run without this leg.
- **Unknown-team fail-closed.** A row whose team does not map to a canonical MLB
  abbreviation is dropped, never guessed.
- **Circuit-breaker friendly.** Registered through the standard `SourceRegistry`,
  so a streak of failures quarantines the source for a few cycles and then
  retries automatically.

### Team mapping

FanGraphs abbreviations are normalized to the repo's canonical MLB abbreviations
(the namespace `parse_sports_contract` emits) via `canonical_mlb_team()`:
`KCR→KC`, `SDP→SD`, `SFG→SF`, `TBR→TB`, `WSN→WSH`, plus the ESPN aliases
`AZ→ARI` / `CWS→CHW` and the `OAK→ATH` relocation fold. Both the book keys and
the market's competitor abbreviations pass through the same function, so lookups
agree regardless of the incoming namespace. An unmappable team resolves to
`None` and abstains.

### From projections to fair value

`autonomy/signals/projection_consensus.py` (`ProjectionConsensusSignal`) prices
MLB **winner** and **total-runs** markets:

- **Offense rate** — a team's projected season runs equal the sum of its
  batters' projected `R` (each run is credited to exactly one scorer), so
  `sum(R) / 162` is a clean lineup-agnostic runs-per-game rate.
- **Defense rate** — the IP-weighted mean ERA of the team's pitchers, scaled by
  `1.08` (unearned-run factor) to total runs allowed. A team with no usable
  pitching projection falls back to a league-average defense (flagged, and the
  emission's uncertainty widens).
- **Expected runs** blend a team's own offense with the opponent's projected run
  prevention (`0.5 * (offense + opp_defense)`), then feed straight into
  `poisson_over_probability` / `poisson_win_probability` from
  `autonomy/sports/baseball.py` — the same functions the incumbent
  `BaseballRunModel` uses. The run model is **reused, not forked**.

**v1 simplification (deliberate):** rates are lineup-agnostic, rest-of-season
TEAM rates — no game-day lineup, announced-starter ERA, or park/weather
adjustment (those already live in `BaseballIntelligenceSignal`). This leg
contributes the orthogonal, results-independent talent prior that projections
add. Emissions widen their error bars accordingly and are weighted lightly until
a contested record earns more.

### Governance

Every emission is stamped `challenger_only=True`, so the forecaster excludes it
from the live execution ensemble until a settlement-backed promotion review.
`promotion_eligible` is **not** hardcoded — eligibility is left to the promotion
engine's evidence-driven decision.

### Snapshot persistence

Each fetched projection is recorded via
`AutonomyLedger.record_external_observation` under `source="fangraphs_<system>"`
(e.g. `fangraphs_steamer`), `series_id="{team}:{playerId}:{system}"`, with the
primary value being wOBA (batters) or ERA (pitchers) and the `q10..q90`
percentiles plus supporting stats in the features JSON. No schema migration —
the existing `external_observations` table is reused. Each cycle's snapshot is a
new point-in-time vintage (`observed_at` is part of the content-addressed row
key); duplicate rows within one snapshot dedup automatically.
