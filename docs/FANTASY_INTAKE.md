# Fantasy-Data Intake Layer

The fantasy layer ingests public projection / fantasy feeds as **internal
challenger evidence** and triangulates them against Dummy's own live models and
market prices. It is a multi-leg build; this document tracks each leg.

| Leg | Source | Status | Module |
| --- | --- | --- | --- |
| #1 | FanGraphs projection consensus | **shipped** | `autonomy/ingest/fantasy/fangraphs.py` |
| #2 | Player props (sportsbook prop lines) | planned | — |
| #3 | ESPN fantasy baseball (flb) ownership / ADP / projections + scratch feed | **shipped** | `autonomy/ingest/fantasy/espn_fantasy.py` |

Leg #2 (props) lands in a later wave; leg #1 is the first fantasy-data source and
the anchor the later legs triangulate against.

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

## Leg #3 — ESPN fantasy baseball (flb) ownership / ADP / projections + scratch feed

### Source

Keyless public ESPN fantasy `kona_player_info` player universe (the same hidden
JSON the fantasy.espn.com player table calls):

```
GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/2026/players
    ?scoringPeriodId=0&view=kona_player_info
header  x-fantasy-filter: <JSON, see below>
```

- Verified keyless and returning enriched data **from this machine** on
  2026-07-16 (3,890 enriched players; ~23k total rows).
- Per enriched player: `ownership{percentOwned, percentStarted,
  averageDraftPosition, auctionValueAverage, percentChange, …}`,
  `draftRanksByRankType{STANDARD, ROTO}`, `injuryStatus`, `proTeamId` (numeric),
  `eligibleSlots`, `defaultPositionId`, and `stats[]` tagged `statSourceId`
  (0 = actual, 1 = projected) / `statSplitTypeId` (0 = season).

**Filter semantics (the load-bearing gotcha, learned at build time).** This
`/players` collection **always** returns the full player universe; the
`x-fantasy-filter` header does **not** truncate the list — it selects which
players get *enriched* with `ownership` / `stats` / `draftRanksByRankType`.
Without a well-formed filter, **zero** players are enriched (every row is the
bare light shape: `id`, `fullName`, `proTeamId`, `eligibleSlots`, … and nothing
else), and this leg fail-closes to empty. The filter that works:

```json
{"players":{
  "filterActive":{"value":true},
  "sortPercOwned":{"sortPriority":1,"sortAsc":false},
  "filterStatsForSourceIds":{"value":[0,1]},
  "filterStatsForTopScoringPeriodIds":{"value":2,"additionalValue":["002026","102026"]}
}}
```

The response header `x-fantasy-filter-player-count` reports how many rows matched
the filter. A `limit` is intentionally omitted (it would only shrink the
enriched set, not the returned list). A row without an `ownership` block is a
light-only row and is **dropped**, never guessed — that is what makes the whole
book fail-closed if the enriched view is ever unavailable (e.g. an IP/Cloudflare
degradation to the light universe).

### Terms-of-service posture

Identical to leg #1: ESPN fantasy data is used **strictly as internal challenger
evidence** — never redistributed, republished, resold, or exposed downstream.
One polite fetch per cycle, a browser `User-Agent`, a bounded timeout. Retired
rather than worked around if automated reads become unwelcome.

### Team mapping

`proTeamId` is numeric. `ESPN_FLB_PRO_TEAMS` (fetched authoritatively from
ESPN's own `proTeamSchedules_wl` settings) maps it to the ESPN abbreviation,
which is then folded to the repo-canonical MLB namespace by **reusing leg #1's**
`canonical_mlb_team()` (`Ath→ATH`, `ChW→CHW`, `Wsh→WSH`, `StL→STL`, `SD`/`SF`/
`TB`/`KC` pass through). Id `0` (free agent) and any unmapped id resolve to
`None` and are dropped.

### From ownership to a crowd lean

`autonomy/signals/espn_fantasy_crowd.py` (`EspnFantasyCrowdSignal`) prices MLB
**winner** markets only. Per team it builds a **public-backing** index
(`Σ percentOwned/100` over meaningfully-owned players) blended with a
**projected-strength** index (`Σ` ESPN projected `appliedTotal`), and turns the
two teams' index differential into a bounded logistic win lean. This is the
orthogonal thing crowd data adds on top of leg #1's talent model: a coarse
"which roster the public + projections back harder" prior, deliberately given a
**wide** error bar. Totals / spread / YRFI are out of scope (ownership carries
no run-margin or first-inning information) — the same boundary leg #1 drew.

### Scratch / availability feed

Each refresh diffs the new player snapshot against the previous one and emits a
typed `ScratchEvent` feed (`FantasyBook.scratch_events()`): an
`availability_change` when a player's coarse availability class flips
(`available` ⇄ `day_to_day` ⇄ `out`, e.g. a bat hitting the DL or a probable
starter's status changing), and an `ownership_swing` when `percentOwned` moves
≥ 5 points between cycles.

**Persistence choice (documented).** The previous snapshot is held **in memory**
on the long-lived `FantasyBook` instance (registered once, refreshed per cycle),
matching the in-memory-only discipline of the sibling injury books
(`InjuryBook`, `LeagueInjuryBook`) and `ProjectionBook`. Ledger read-back is
available (snapshots *are* recorded) but heavier and unnecessary for a
consecutive-cycle diff; runtime-state disk persistence was rejected to avoid
touching `runtime/` and to stay consistent with those books. On the first cycle
(or after a restart) there is no prior snapshot, so **no** events fire —
fail-closed. A failed/empty refresh preserves the prior snapshot rather than
overwriting it, so a transient outage can never manufacture a wave of phantom
"everyone scratched" events on the next good cycle.

**Integration choice (documented).** The scratch events are exposed as **their
own typed feed**, not injected into the existing injury machinery, and not
wired into the opportunist's assessment schema on this branch. Rationale:
`InjuryBook` / `LeagueInjuryBook` are keyed by normalized **team name** and
model team-level burden from the ESPN *injuries* feed — they have no per-player
identity slot and no notion of a change event, and expanding them risks
perturbing the byte-identical MLB burden numbers `BaseballIntelligenceSignal`
depends on (explicitly out of bounds per `players.py`'s own docstring). The feed
is instead shaped to mirror the opportunist's existing evidence-only
`ejection_events` (raw ESPN observations, never a trigger predicate or a
probability adjustment), so a future wire-up can attach scratch events to a
`MispricingAssessment` the same way — without this branch touching
`mispricing.py`'s schema (which would collide with sibling Wave-2 branches).

### Governance

Every emission is stamped `challenger_only=True`; excluded from
`forecaster.fuse()` until a settlement-backed promotion review.
`promotion_eligible` is **not** hardcoded — left to the promotion engine's
evidence-driven decision (base-branch convention). Registered in `session.py`
right after `ProjectionConsensusSignal`; taxonomy home `espn_fantasy_crowd → mlb`
(the registry-completeness tripwire fails without it).

### Snapshot persistence

Each fetched player is recorded via `AutonomyLedger.record_external_observation`
under `source="espn_flb"`, `series_id="{team}:{playerId}:flb"`, value =
`percentOwned` (`unit="percent_owned"`), with ownership / ADP / `injuryStatus` /
availability / projected total in the features JSON. Each scratch event is
likewise recorded under `source="espn_flb_scratch"`. Each cycle is a new
point-in-time vintage (`observed_at`); no schema migration — the existing
`external_observations` table is reused.
