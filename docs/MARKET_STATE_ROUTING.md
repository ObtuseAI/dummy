# Market-State Routing (L1)

How dummy resolves *"who governs this market"* — one specialist per market,
by vertical/league, each with its own pricing logic and its own idea of
in-season vs offseason. This layer is already shipped (council build-out
Phase 0 + seasons); this document makes it explicit for anyone mapping the
Phenon Autopoietic Harness's "Ontological Market Manifold" concept onto real
code. Nothing here is new behavior — it is a description of what runs today.

## One specialist per market

`autonomy/specialists/base.py::SpecialistRegistry` holds an ordered list of
specialists. `route(market)` walks the list and returns the first specialist
whose `applicable(market)` is true; registration order is routing order, and
series prefixes are disjoint by design so **at most one specialist ever
claims a market**. A specialist that raises during `applicable`/routing/
warmup is skipped — one broken vertical can never take the council down
(`route`, `on_cycle_start`, and `health_report` all swallow per-specialist
exceptions).

`autonomy/specialists/factory.py::build_specialist_registry` assembles the
registry over the brain's already-registered signal instances (no second
copy of model state): `MlbSpecialist` first, then a `TeamLeagueSpecialist`
per league in `TEAM_LEAGUES = ("nba", "nfl", "ncaaf", "nhl", "ncaamb")`, then
`CryptoSpecialist` last. Each specialist's `applicable()` parses the market
through the real contract parser (`parse_sports_contract` for sports,
`parse_crypto_ticker` for crypto) rather than a hand-rolled prefix check, so
routing is exercised exactly the way the forecast/book calls use it.

`autonomy/taxonomy.py::specialist_for(source)` is the matching *label*
resolver used downstream (grading, CLV, the strategy miner, the promotion
registry): an exact-match table (`SOURCE_TAXONOMY`) for sources whose
emitted name doesn't carry a league prefix, falling back to prefix rules
(`crypto_`, `mlb_`, `nfl_`, `ncaaf_`, `ncaamb_`, `nba_`, `nhl_`, `wnba_`; a
`ufc_`/`f1_` prefix still resolves to the literal label `"retired"` since
those verticals were retired 2026-07-12) and finally to `"other"` when
nothing matches. A registry-completeness test asserts no *registered* signal
source ever resolves to `"other"` — that is the tripwire for a new signal
shipping without a taxonomy home.

## Per-vertical governing logic

Each specialist wraps genuinely different math — routing exists precisely
because crypto and sports are not the same problem:

**Crypto** (`autonomy/specialists/crypto.py::CryptoSpecialist`)
- `forecast()` delegates to the registered `CryptoSpotVolSignal` champion: a
  driftless **lognormal** model over time-to-close, sigma from realized
  volatility off public Coinbase candles (`autonomy/signals/crypto_spot.py`).
- `book()` delegates to `autonomy/crypto_implied_book.py::CryptoImpliedBook`
  — an independent risk-neutral P(above strike) derived from **Deribit's
  DVOL** implied-volatility index (forward-looking) rather than the
  champion's own realized-vol view, giving crypto the same model-vs-book
  triangulation MLB gets from its sportsbook line. Fail-closed to
  `model_only` on a missing/unwired book or stale (>6h) DVOL.
- `autonomy/crypto_events.py` layers a small, static, auditable calendar of
  scheduled macro windows (FOMC meeting days) that **widen uncertainty
  only** (`EVENT_UNCERTAINTY_BUMP`) while a window is active — it never
  shifts the mean, and outside every window the bump is exactly 0.0.
- Grading horizon is derived per `autonomy/taxonomy.py::horizon_bucket`:
  native `15m` contracts (detected by ticker series token), else `hourly`
  (≤3h to close) or `daily+`, so a source's trust is scoped correctly across
  three very different time regimes rather than pooled into one.
- `live_forecast()` abstains unconditionally — crypto contracts are
  continuously repriced by the champion model; there is no separate
  in-play phase the way a sports game has one.

**Sports** — one `TeamLeagueSpecialist` instance per league (NBA, NFL,
NCAAF, NHL, NCAAMB) plus the dedicated `MlbSpecialist`, each routing through
`parse_sports_contract` and delegating to a league-specific kernel:

| League | Module | Governing logic |
|---|---|---|
| MLB | `autonomy/sports/baseball.py` | Plate-appearance-level run distribution: EWMA offense/prevention, first-inning tendencies, venue run environment, announced-starter ERA, RE24-style base-out run expectancy |
| NFL | `autonomy/sports/nfl_margin.py` | Key-number-tilted margin PMF (field goals/touchdowns spike the real distribution); winner + full spread ladder derive from ONE exponentially-tilted distribution so they stay coherent by construction |
| NCAAF | `autonomy/sports/college.py` | College-specific compound-Poisson score-event kernel shared with the live scoring grammar; coherent winner/spread/total PMFs plus an Elo talent-gap prior blended with season form |
| NBA | `autonomy/sports/nba_model.py` | Pace × efficiency (EWMA offensive/defensive rating per 100 possessions, shared pace EWMA); heteroskedastic dispersion scaling with `sqrt(pace/99.5)`; bounded rest engine + garbage-time cap |
| NCAAMB | `autonomy/sports/college.py` | Reuses the NBA pace × efficiency engine wholesale via a college parameter set (different cold-start constants) |
| NHL | `autonomy/sports/nhl_model.py` | Independent-Poisson goal model per side over one regulation-goal matrix, with an explicit OT/shootout branch (Kalshi settles on final score including OT/SO) and goalie-identity (save-percentage) adjustment |

Per-league `book()` sources an independent sharp line: every team specialist
prefers an ESPN-summary live de-vig for an in-progress winner, spread, or total
and falls back to pre-game sportsbook consensus when applicable. Spread/total
coverage is exact-line only; unmatched alternate strikes abstain.
`live_forecast()` is wired for MLB, NBA, NFL, NCAAF, NHL, and NCAAMB, gated on
`game.status == "in"` plus each signal's own point-in-time score/clock checks.
MLB additionally emits separately graded `mlb_pa_live_*` opinions when the
StatsAPI plate-appearance context passes its lineup/starter/coverage gates.

Every kernel here is explicitly **challenger-only** (`features
["challenger_only"] = True`) and fail-closed: missing ESPN data returns
`None` straight through, byte-identical to the engine being disabled.

## Season wake/sleep gating

`autonomy/specialists/seasons.py::SeasonMonitor` decides whether a league is
worth routing to right now, purely from ESPN's own scoreboard — no
hardcoded calendar to rot. A league is **active** when any game appears in a
`-7/+21` day window (`LOOKBACK_DAYS`/`LOOKAHEAD_DAYS`) around now; verdicts
are TTL-cached (`CHECK_TTL_HOURS = 6.0`) and persisted to
`runtime/autonomy/season_state.json` (read-merge-write, since several
monitors share the file) so restarts remember.

The gate reads via `games_or_raise` rather than the ordinary `games` method
specifically so it can tell "offseason" from "feed down": `games` swallows
fetch failures into an empty list (correct for every forecasting path, which
must never crash on a bad fetch), but that same empty list is indistinguishable
from a genuine offseason — exactly the ambiguity the season gate cannot
tolerate. `games_or_raise` raises instead, so `SeasonMonitor.active()` can
catch the exception and keep the **last known verdict** (sticky-on-error)
rather than reading a transient blip as "season over." A league never
checked successfully defaults to **active** — fail-open on wasted warmup
cost, never fail-closed on a live league going dark. (This gate is about
efficiency and health truth, not capital safety: challenger-only status and
fail-closed signal behavior already guard capital regardless of season
state.) There is deliberately no wake backfill — a genuine wake has no
completed games behind it to backfill, and a false-dormant blip is bounded
by the TTL and covered by the signals' own recent-days warmup window.

`TeamLeagueSpecialist.health()` reports `"dormant"` (not `"cold"` or `"ok"`)
when its league's `SeasonMonitor.active()` is false, so the council's health
report distinguishes an offseason league from a genuinely broken one.

## The 3×3 conviction lattice sitting on top

`autonomy/coherence.py` builds a nine-cell lattice per game from the
specialists' own already-computed forecasts: three estimators (the routed
specialist's model, its de-vigged sharp book, the Kalshi crowd price) crossed
with three market families (winner, spread ladder, total ladder). Grouping
goes through the same `parse_sports_contract` the specialists use, so a
market that doesn't parse to a sports contract (or whose family isn't
winner/spread/total — e.g. MLB's YRFI) simply isn't grouped: fail-closed by
construction.

Two independent checks feed a per-game conviction tier:
- **`ladder_violations`** — Kalshi's own rung prices should be
  non-increasing as the covered margin/line gets harder, within one
  same-team ("subject") ladder, beyond a small fee-band slack; needs no
  model opinion at all.
- **`cross_family_incoherence`** — the winner price and the spread-ladder
  price should reconcile through the specialist's own joint-distribution
  shape (a documented first-order linear transport), subject-aware so
  opposite sides of the same spread are never mistaken for confirming one
  another.

`lattice_conviction` folds both into one of four tiers, richest first:
`TIER_STRUCTURAL` (an exchange-internal contradiction — needs no forecast to
trust), `TIER_CROSS_CONFIRMED` (model, book, and market-internal structure
all agree, same team, ≥2 families), `TIER_MODEL_BOOK`, or `TIER_MODEL_ONLY`.
The mispricing monitor surfaces `structural`/`cross_confirmed` counts every
pass as the highest-conviction subset of its shortlist.

## Phenon vocabulary → dummy modules

| Phenon concept | Dummy reality | Status |
|---|---|---|
| L1 "Ontological Market Manifold" (per-market reality state routing) | `autonomy/specialists/base.py::SpecialistRegistry` + `autonomy/taxonomy.py::specialist_for` route every market to exactly one specialist by vertical/league, each with its own pricing logic (this document) | **Shipped** |
| L2 "Athletic Quant" (external power-ratings ensemble vs. Kalshi) | `autonomy/sports/power_ratings.py` + `PowerRatingsSignal` in `autonomy/signals/sports_intelligence.py` — keyless ESPN FPI/BPI plus point-in-time Elo consensus, with separate `power_ratings_<league>` challenger emissions and bounded `power_divergence` evidence | **Shipped, challenger-only** (no automatic promotion; each grading scope still must earn the documented forward contested-Brier record and receive explicit human promotion) |
| L3 "Evolution Engine" (deconstruct losses → propose → integrate) | Split across four shipped modules: `autonomy/strategy_miner.py` *discovers* candidate edges from past/missed trades; `autonomy/loss_engine.py` *deconstructs* settled cluster-level Brier shortfall and supplies a non-gating tuner priority plus dashboard evidence; `autonomy/tuner.py` *proposes* better parameter values; `autonomy/promotion.py` *integrates* a challenger into the live ensemble, but **only on an explicit human-authored edit to `runtime/autonomy/promotions.json`** — promotion is human-only, and the only automatic transition in this whole chain is one-way-safe auto-demotion | All four modules **shipped**; loss attribution is chained after the nightly strategy miner and CLV grader and writes only `runtime/autonomy/loss_attribution.json` |

No component described above writes execution logic, promotes a challenger,
or moves capital on its own. Everything in the mapping table upstream of a
human promotion decision remains challenger-only and fail-closed, per the
doctrine already documented in `docs/AUTONOMY.md`.
