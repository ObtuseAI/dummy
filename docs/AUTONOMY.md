# Dummy Autonomy Layer

Shipped 2026-07-08. The predator loop: scan → signal → forecast → allocate →
risk → execute → reconcile → learn. The dashboard is observational only;
operator ceremonies and process control stay outside its HTTP surface.

## Operator dashboard + alerts

```bash
python scripts/run_dummy_dashboard.py --port 8787   # open http://127.0.0.1:8787/
```

Loopback-only, read-only page: liveness/heartbeat, live-canary gate + blockers, risk state,
per-source calibration scoreboard, recent cycles, bankroll curve, and alerts.
Alerts (`autonomy/alerts.py`) fire once per episode on SELF_STOP, drawdown
ladder deepening, evidence-gate-green, and cycle-error streaks — written to
`runtime/autonomy/alerts.jsonl` and surfaced on the dashboard.

`scripts/run_dummy_dashboard.py` → `autonomy.dashboard` is the only supported
HTTP entrypoint. The former root `main.py`, `dashboard.backend`, WebSocket
status adapter, and browser-facing operator mutation routes were retired rather
than retained as compatibility shims. Operator and authority ceremonies remain
explicit CLI workflows.

Core API surfaces:

- `GET /api/status` — fast precomputed snapshot. Reads only the fresh runtime
  JSON artifacts plus `watchdog_status.json`; it NEVER opens `ledger.db`.
  Every panel payload carries `data_ages` (per-artifact timestamp, age in
  seconds, cadence-derived threshold, `stale` flag) so stale data is visibly
  stale instead of rendering as healthy.
- `GET /api/autonomy` — the full evidence report (includes a 1,000-resample
  cluster bootstrap over the ledger). It is cached for 120 s and computed on a
  background worker with a bounded request deadline
  (`DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS`, default 20 s). A cold request
  that misses the deadline gets the last cached value marked
  `stale_cache: true`, or a `503` pointing at `/api/status` when no cache
  exists yet — it no longer blocks for minutes recomputing the bootstrap
  inline. The dashboard UI falls back to `/api/status` automatically.
- `GET /api/bet_board` and `GET /api/tier-performance` — artifact-only guide
  and issued-tier evidence. They never scan the multi-gigabyte ledger on a web
  request. Missing or invalid artifacts return `503`; stale artifacts remain
  visible with explicit age/stale labels. `UNATTRIBUTED` means a legacy or
  unverifiable row, not WATCH, and is excluded from tier claims.

Tier performance is forward-only and policy-version-separated. Forecast skill
uses one receipt-bounded fused emission per settled market; realized economics
require a prior witnessed positive fill and use witnessed cost/fees. Hit rate,
Brier, log loss, calibration, market-relative skill, P&L, ROI, profit factor,
and drawdown remain separate. A cohort needs at least 30 rows across at least
10 independent event clusters before it is labelled sample-available.

## Supported prediction targets

The active prediction surface is sports and crypto. Every other market category
is excluded from forecasting, ranking, trade proposals, and execution. That
boundary is enforced independently in target classification, the bet board,
active strategy registry, autonomous/hybrid paths, and the central live
firewall.

## Ops watchdog (aggregate fleet monitor)

`autonomy/watchdog.py` + `scripts/run_dummy_watchdog.py` read each scheduled
task's freshest artifact, compare its age against 2x that task's cadence, and
check environmental floors: trailing CYCLE_ERROR streak in `cycles.jsonl`
(threshold 3), `ledger.db` size ceiling (default 12 GB), operator kill-file
presence, and a free-disk floor (default 10 GB). Results are written to
`runtime/autonomy/watchdog_status.json` (consumed by the dashboard) and fire
rising-edge, de-duplicated alerts through `autonomy/alerts.py`
(`WATCHDOG_TASK_STALE`, `WATCHDOG_CYCLE_ERROR_STREAK`, `WATCHDOG_LEDGER_SIZE`,
`WATCHDOG_KILL_FILE`, `WATCHDOG_DISK_FLOOR`). The watchdog is read-only over
the runtime tree: it never opens `ledger.db` and never controls a task.

```bash
# One pass (exit code 1 when unhealthy):
python scripts/run_dummy_watchdog.py

# Register the 5-minute scheduled task ONCE, elevated — the OPERATOR runs
# this; nothing registers it automatically:
powershell -ExecutionPolicy Bypass -File scripts/install_watchdog_task.ps1
```

Watched tasks and thresholds (stale = artifact older than 2x cadence, or the
artifact/timestamp is missing — fail-closed):

| task | artifact | cadence | stale after |
|---|---|---|---|
| DummyShadowPredator | heartbeat.json (`last_cycle_at`) | 10 min | 20 min |
| DummyMispricingMonitor | mispricing_monitor_latest.json (`generated_at`) | 5 min | 10 min |
| DummyCryptoPaperTwin | crypto_paper_twin_latest.json (`completed_at`) | 5 min | 10 min |
| DummySportsSimulation | sports_simulation_latest.json (`completed_at`) | 10 min | 20 min |
| DummySimulationTrainer | simulation_training_latest.json (`created_at`) | 60 min | 2 h |
| DummyStrategyMiner | strategy_mining_report.json (`generated_at`) | daily | 48 h |
| DummyReadinessReport | readiness_report.json (`generated_at`) | daily | 48 h |

## Stale-data submit gate (fail-closed)

The executor refuses any order whose driving market-book snapshot is older
than a per-horizon maximum age at the moment of submit
(`autonomy/staleness.py`; the scanner stamps `MarketView.fetched_at` once per
sweep). Refusals are recorded as `BLOCKED_LOCAL` outcomes in the ledger with
the reason, age, and threshold — never a silent skip — and counted on
`Executor.stale_block_count`. Defaults:

| horizon | max snapshot age |
|---|---|
| crypto 15m (and faster) | 60 s (matches the 1-min resting-quote TTL) |
| crypto hourly and longer | 180 s |
| sports live / in-play | 120 s |
| sports pregame | 300 s |
| everything else | 300 s |

Unknown freshness is stale: a missing, unparseable, or future snapshot
timestamp refuses the order. A LIVE submit additionally requires a positive,
current venue-health witness at the moment of submit (`/exchange/status`), not
just at cycle start. This check fails closed: a missing, failed, or malformed
status fetch BLOCKS the order (`exchange_status_unavailable_at_submit` in
`autonomy/executor.py`), as do maintenance (`exchange_maintenance_at_submit`)
and halt (`trading_halted_at_submit`) states. Unknown is not permission at
submit time. The fail-open doctrine (status probe failure → proceed) applies
only to the cycle-start probe in `autonomy/exchange_status.py`, which decides
whether the learning loop runs — never whether an order submits.

## Shadow paper-evidence engine + going live (Tier 1)

```bash
# The scheduled shadow entry point runs the FULL paper predator cycle on every
# invocation (scripts/run_dummy_shadow_daemon.py -> autonomy.daemon.run_one_cycle
# in SHADOW mode). It is the authoritative paper-evidence engine: it produces
# new paper orders, signals, and settlements, and the autonomous promotion
# evaluation treats its heartbeat as a mandatory rail
# (autonomy/auto_promotion_runner.py). The watchdog labels DummyShadowPredator
# "authoritative shadow cycle (paper evidence engine; promotion rail input)".
python scripts/run_dummy_shadow_daemon.py

# What IS retired is paper-results AUTHORITY over live trading
# (autonomy/session.py: PAPER_RESULTS_AUTHORITY = "RETIRED_NON_AUTHORITATIVE").
# Every shadow record is stamped paper_results_authority +
# execution_authority=false: shadow results can neither enable nor block a
# LIVE start.
python scripts/run_dummy_backtest.py --bootstrap
python scripts/run_dummy_autonomous.py canary        # retired paper audit report (no live authority)

# A LIVE session remains BLOCKED until the separate one-controlled-proof
# live-submit config, typed/environment acknowledgements, command seal,
# protected caps registration, central-firewall descriptor, local credential
# resolver, and unused proof lock all pass. Paper/shadow results are not part
# of that authority decision. Paid model research is a separate two-key
# control: configs/model_routing.json must contain the literal JSON value
# live_model_calls_enabled=true AND the same process must explicitly set:
set DUMMY_DEBATE_LIVE=1
# Neither model-call key grants probability, capital, or order authority.
python scripts/run_dummy_autonomous.py start --live --hours 6 --ack "<exact ack>"

# Stop everything, instantly:
python scripts/run_dummy_autonomous.py stop
```

`autonomy/canary.py` results are `RETIRED_NON_AUTHORITATIVE`: they can neither
enable nor block a LIVE start. The shadow daemon and the monitor loops keep
producing new paper evidence — that production is deliberate (the promotion
evaluation and readiness proof depend on it), and only its authority over live
trading is retired. LIVE authority remains fail-closed under the explicit
one-proof, operator, caps, command-seal, central-firewall, credential, and
proof-lock contracts; there is no paper-results override flag.

## Commands

```bash
# Status (session, kill switch, live controls, and retired audit history):
python scripts/run_dummy_autonomous.py status

# LIVE session: requires the exact typed acknowledgement.
python scripts/run_dummy_autonomous.py start --live --hours 24 --ack \
  "I authorize an autonomous Dummy trading session with self-managed risk under the LiveBrokerFirewall, LIMIT orders only, until I stop it"

# Stop: writes runtime/autonomy/KILL and disarms the session. Instant.
python scripts/run_dummy_autonomous.py stop
```

## Council of specialists

Council build-out (WS-8, WS-9, WS-14, WS-15). Every vertical — MLB, NBA, NFL,
NCAAF, NHL, NCAAMB, and crypto — is owned end-to-end by its own subagent
behind one protocol (`autonomy/specialists/base.py`: `Specialist` /
`SpecialistRegistry`): `applicable`/`forecast`/`live_forecast`/`book`/
`ejection_events`/`on_cycle_start`/`health`. `autonomy/specialists/factory.py` assembles the
registry over the brain's already-registered signal instances (no second copy
of the model state); registration order is routing order, and series prefixes
are disjoint by design so at most one specialist ever claims a market. A
specialist that raises during routing or warmup is skipped — one broken
vertical can never take the council down.

**Live team-sport triangulation.** MLB and all five team-league specialists
expose their in-play winner, spread, and total models to the mispricing
monitor. `EspnSummaryBook` reads one event-summary cache and de-vigs the
two-way `pickcenter` moneyline, point spread, or over/under. Spread and total
odds use the observed de-vigged price when ESPN's current main line exactly
equals the Kalshi strike. ESPN exposes only one current public main
spread/total, so unmatched alternate rungs use an explicit league-width normal
curve anchored to that de-vigged main price. This translation remains
challenger evidence; malformed or one-sided books still abstain.
NBA uses its residual score model, while NHL uses a positive-shared-component
bivariate Poisson that preserves both team marginal goal means and scales the
shared component down with live time. NFL and NCAAF use distinct
compound-Poisson regulation distributions, and NCAAMB uses its own
40-minute/two-half normal remainder model (`autonomy/sports/live_team_models.py`).
All winner, spread, and total views remain challenger-only and fail closed on
missing score/period/clock. NFL and NCAAF overtime fetch ESPN summary state only
when the scoreboard enters period 5 or later: `drives.current` identifies the
possessing team and `drives.previous` proves completed possessions. NFL applies
the 2025 guaranteed-initial-possession structure followed by sudden death;
NCAAF keeps the first two alternating possessions separate and switches to
paired two-point attempts from the third overtime. Missing possession history
abstains rather than inferring it from the score. The summary play feed also
supplies raw ejection observations when ESPN publishes an explicit play. Each
observation records the source event time and
the monitor's receipt time and is surfaced as opportunist evidence only: it
does not shift a probability, widen uncertainty, change a strike gate, or
create execution authority. Article prose is excluded as postgame knowledge.

**MLB StatsAPI PA live challenger.** When a live MLB event can be matched to
StatsAPI and has confirmed nine-player lineups, both starters, and at least
75% batter-rate coverage, `BaseballIntelligenceSignal` runs the deterministic
plate-appearance simulator once per game/cycle. Its expected home/away runs
condition the observed score and remaining innings, while the existing
division/rivalry table applies the bounded winner regression. These opinions
use distinct `mlb_pa_live_winner|total|spread` source names and model version
`mlb_pa_sim_live_v1`, so they accrue a new forward record instead of rewriting
the incumbent `mlb_live_*` evidence. Missing hydration fails back to the
incumbent source. All outputs remain challenger-only and human-promotion-only.

**Forward live-evidence accumulation.** The `DummyMispricingMonitor` runs the
live specialist path every two minutes, while `DummySportsSimulation` runs the
paper simulation path every ten minutes. They record only naturally occurring,
point-in-time emissions and later settlements; an inactive league, unmatched
market, missing possession/lineup state, or empty live slate remains an honest
zero. Retro rows, synthetic games, and lower-quality substitutes cannot be
inserted to satisfy an evidence counter. Nightly strategy-mining and readiness
tasks consume the resulting settled rows without promoting a source.

**Loss attribution.** `autonomy/loss_engine.py` deconstructs settled,
market-benchmarked forecast history by grading scope and event cluster, surfaces
the worst adequately sampled feature regimes, and supplies only a non-gating
priority order to the tuner. The nightly strategy-miner task runs it after the
miner and CLV grader. It writes `runtime/autonomy/loss_attribution.json`; it
cannot mutate model constants, source weights, promotions, execution, or capital.

**Season gating.** `autonomy/specialists/seasons.py`'s `SeasonMonitor` decides
whether a league is active from ESPN's own scoreboard (any game inside a
-7/+21 day window means active) — no hardcoded calendar to rot. Verdicts are
TTL-cached (6h) and sticky-on-error (a feed blip keeps the last known verdict
rather than silently benching a live league), persisted to
`runtime/autonomy/season_state.json` so restarts remember. A league never
checked successfully defaults ACTIVE (fail-open on cost, not fail-closed on
capital — challenger-only + fail-closed already guard capital).

**CLV grading (WS-8).** `autonomy/clv.py` grades every paper entry against
the sharp book's closing line (~10x faster feedback than waiting on
settlement): a book tape (one row per assessed market per monitor pass) plus
close selection within a window, aggregated as `clv_bps` per
`(specialist, market_type)` with per-event-cluster confidence intervals
(never per-row — correlated same-event entries would shrink the interval
dishonestly). **CLV feeds the autonomous promotion ladder as criterion (e)**
(since 2026-07-16: a scope with CLV instrumentation must show a CLV mean CI
lower bound > 0; a scope without it faces a higher cluster bar instead — see
`docs/AUTO_PROMOTION.md`). Settlement-backed contested Brier
(`autonomy/backtest.py`, taxonomy-keyed via
`autonomy/taxonomy.py`'s `grading_scope`) remains the primary gate, and
`autonomy/backtest.py`'s `trust_surface_by_specialist` rolls the per-scope
contested-Brier record up to one (specialist, subject, market_type, phase)
surface for
human review.

**Propose-then-promote tuner (WS-9).** `autonomy/tuner.py` proposes better
sigma/edge scalars for the sports engines into one artifact
(`runtime/autonomy/tuning_proposals.json`) and never writes a constant back
into a `.py` file — the walk-forward winner is picked on TRAIN only and
evaluated once, out-of-sample, on TEST, with per-event-cluster means (not
per-row) feeding the reported confidence interval. A human reads the artifact
and edits the source constant in a reviewed PR; the tuner's own test suite
asserts source-file hashes are byte-identical before and after a full run.

**Promotion registry (WS-14) + autonomous thresholded promotion (2026-07-16).**
`autonomy/promotion.py` is the only path a challenger scope can ever reach the
live ensemble. By owner directive 2026-07-16, positive promotion is no longer
human-only, but it remains fail-closed: the `AutoPromotionEngine`
(`autonomy/auto_promotion.py`, run daily inside the readiness task by
`autonomy/auto_promotion_runner.py`) promotes a scope into fusion only when it
clears the predictive gates plus receipt-bounded, post-registration, isolated
witnessed-fill net P&L across enough independent forward event clusters.
Midpoint/maker counterfactual P&L is a research diagnostic only and grants no
fusion authority. Evidence that is promising but incomplete is reported as a
zero-weight human-review candidate — see `docs/AUTO_PROMOTION.md` for every
threshold, rail, and the full rationale.
Stage 1 fuses at a capped probation weight (25% of earned trust); stage 2
(full weight) requires realized scope-attributed trade P&L. Every promotion,
escalation, and demotion is recorded in an append-only hash-chained ledger
(`runtime/autonomy/promotion_ledger.jsonl`) with the full evidence dossier,
alerted via `autonomy/alerts.py`, and surfaced on the dashboard state JSON.
*Demotion remains automatic, instant, and one-way-safe*
(`runtime/autonomy/auto_demotions.json` — reducing risk never waits). A
missing or corrupt promotions file still means nobody is promoted.

**Scope of the directive: fusion membership only.** Live trading
authorization — `configs/live_submit.json`, the second-proof sequence, and
session live auth — remains **operator-gated** and is untouched by the
autonomous ladder.

Promotion and readiness scopes are exact four-axis cohorts:
`source | subject | market_type | horizon_or_phase`. `subject` is the crypto
asset, sports league, or exact contract series. The daily evaluator accrues
evidence and evaluates gates autonomously for each cohort; it never pools BTC
with ETH, MLB with another league, winner with spread/total/YRFI-NRFI, or
pregame with live. A legacy broad promotion entry without `subject` fails
closed. Negative evidence can autonomously contract or demote only that exact
cohort.

**Dashboard council panel (WS-13).** The operator dashboard is a read-only
process over runtime JSON files — it never holds a live `SpecialistRegistry`
or `SeasonMonitor`. The mispricing monitor (which already builds and cycles a
live council every pass) writes `runtime/autonomy/council_snapshot.json`
(`autonomy/council_snapshot.py`: per-specialist status, season/health details,
open-opportunities count for that pass); the dashboard reads that file plus
the same `season_state.json` `SeasonMonitor` itself persists, and rolls up
`trust_surface_by_specialist` + the CLV report's `scopes` by specialist name.
Absent the snapshot file, the panel is simply empty — never a crash.

**L1 market-state routing.** How `SpecialistRegistry` routes each market to
exactly one specialist, per-vertical governing logic (crypto vs. sports),
`SeasonMonitor` wake/sleep gating, and the 3×3 conviction lattice are
documented in full in `docs/MARKET_STATE_ROUTING.md`.

## Architecture

| Module | Role |
|---|---|
| `autonomy/scanner.py` | Series-targeted sweep of live Kalshi markets; normalizes the dollars-string field schema. Production prediction selection is constrained by `autonomy/target_policy.py` to crypto and sports contracts only |
| `autonomy/target_policy.py` | Canonical fail-closed target policy: weather and commodity contracts are contextual data only and are rejected by selection, fusion, board publication, execution, and the live firewall |
| `autonomy/signals/weather_openmeteo.py` | Retired prediction compatibility shell plus reusable Open-Meteo parsing/fetch helpers. Weather may inform sports context, but the class cannot emit a forecast or authorize an order |
| `autonomy/signals/crypto_spot.py` | Coinbase public candles → realized vol → driftless lognormal strike probabilities for KXBTC*/KXETH* |
| `autonomy/signals/market_prior.py` | The book's own mid as a Bayesian anchor, weight decaying with thinness |
| `autonomy/signals/sports_elo.py` + `autonomy/sports/` | ESPN public feeds + persistent per-league Elo (home edge, K per sport); win-probability for single-game moneylines; self-retrains from finished games each cycle. **MLB is pitcher-aware**: the probable starters' ERAs (from the scoreboard) shift each team's effective Elo, so an ace can overcome a road disadvantage |
| `autonomy/signals/sportsbook.py` | De-vigged sportsbook moneyline (both sides, vig removed) from the scoreboard's embedded book odds, plus **steam**: the open→current line movement in probability space. The sharpest public game forecast, and the trap detector when Elo fights the book |
| `autonomy/signals/sports_intelligence.py` + `autonomy/sports/{baseball,team_scores}.py` | Point-in-time MLB winner/total/spread/YRFI-NRFI and NFL/NCAAF/NHL/NBA/NCAAB winner/total challengers (UFC and Formula One retired 2026-07-12). Models update only from completed public results and remain excluded from execution pending scope-specific forward promotion |
| `autonomy/sports/simulation.py` | Paper-only multi-sport game engine: deterministic replay, Monte Carlo uncertainty, fog-of-war/meta-shift/boss-chaos arenas, Rookie→Boss curricula, evidence-gated mutation skill trees, event-purged walk-forward genome tournaments, paired-cluster bootstrap, Brier/log loss/ECE/MCE/AUC/sharpness/Sortino/drawdown analytics, and zero code/weight/risk/order/capital authority |
| `autonomy/signals/crypto_spot.py::CryptoEwmaTailSignal` | Challenger crypto model beside the champion: EWMA (RiskMetrics) volatility + a variance-matched two-regime fat-tail mixture. Champion/challenger under separate source names — the contested record decides who earns fusion weight; models evolve by selection, not faith |
| `autonomy/signals/crypto_indicators.py` | Shared Coinbase/Kraken/Deribit state plus quarantined empirical-regime, bounded technical-composite, and DVOL probability challengers; technical shifts are capped at 0.45 horizon sigma and never enter fusion without explicit promotion |
| `autonomy/signals/crypto_ta_foundry.py` | Clean-room Dopey-inspired OHLCV challenger: ATR-normalized momentum, Bollinger/stochastic location, OBV/volume anomalies, close location, and breakout/fakeout confirmation; sparse, capped at 0.35 horizon sigma, and separately graded by exact crypto cohort |
| `autonomy/tape.py` | Tape reader: momentum / volume-surge / range-position / spread from 1-minute candlesticks, fed as context to the LLM debate panel on top-K markets |
| `autonomy/exchange_status.py` | Venue awareness: exchange down (maintenance) → the cycle skips with an honest `CYCLE_SKIPPED_EXCHANGE_MAINTENANCE`; trading paused (overnight halt) → the full learning loop runs but zero orders are placed; status probe failure → proceed (unknown is not down) |
| `autonomy/signals/cross_venue.py` | Exact team-set+date matching through Gamma discovery, then public CLOB token-level midpoint/spread/top-depth pricing; Gamma outcome price is fallback only |
| `autonomy/live_book.py` | Signed Kalshi WebSocket orderbook (snapshot+delta state machine) + fixed-point/legacy REST normalization + synchronous pre-submit guards for crossed, behind-best, and >50-contract queue-ahead quotes |
| `autonomy/debate.py` | Exact four-model OpenRouter research panel (Gemini 3.6 Flash, GPT-5.6 Luna, Claude Sonnet 5, and GLM-5.2) with independent bounded roles and a revision round; an incomplete or substituted panel is discarded, and model probability authority remains zero until separately earned from exact-scope forward evidence |
| `autonomy/weather_calibration.py` | Legacy historical weather-data quality and bias analysis. It is retained for contextual research only and does not produce an eligible prediction target |
| `autonomy/signals/commodities_spot.py` | Retired prediction compatibility shell plus reusable WTI/natgas/gold spot and realized-volatility data helpers. Commodity data may inform crypto macro context, but commodity contracts cannot be forecast or traded |
| `autonomy/correlation.py` + risk brain group caps | Collapses correlated markets (adjacent strike buckets, one city-day, both game sides) into one cluster; per-cluster exposure + position-count caps stop the bankroll piling onto one underlying |
| `autonomy/tier_policy.py` + `autonomy/bet_board.py` | Versioned daily-guide quality tiers based on the best quoted side after a conservative one-contract taker fee: A >=4% with uncertainty <=12%, B >=2%/18%, C >=1%/25%, otherwise WATCH. A current letter also requires a valid two-sided selected-side quote and positive depth witnessed by both selected-side Kalshi `*_size_fp` values; positive legacy liquidity is an explicit fallback. The selected sizes, effective depth, and depth source are frozen into the v5/schema-4 snapshot, so v4 and older rows stay unattributed. A is capped at one per correlated event and five per league/asset. The frozen value side and policy hash are display/research metadata only and never grant execution authority |
| `autonomy/tier_performance.py` | Forward-only issued-tier evidence: one receipt-bounded fused forecast per settled market for value-side hit rate/Brier/log loss/calibration, kept separate from settled decisions with a prior witnessed fill for P&L/actual-cost ROI/profit factor/drawdown. Policy versions never pool and legacy rows are never retroactively relabelled |
| `autonomy/backtest.py` | Leakage-resistant replay: decision-time source grading, ECE/MCE, event-cluster bootstrap confidence intervals, strict chronological stability folds, point-in-time walk-forward threshold selection, verified realized P&L/drawdown/profit factor, fill analytics, and derived trust weights |
| `autonomy/drift.py` | River ADWIN diagnostic over ordered Brier excess; reports local negative regime shifts and can block scale, but never changes weights or orders |
| `autonomy/statistics_intake.py` | Public BLS macro, Deribit DVOL, and NWS station observations stored as deduplicated raw facts with timestamps, units, and provenance; no probability conversion |
| `autonomy/portfolio_challenger.py` | OR-Tools CP-SAT report-only candidate selection with budget, payout sanity, event-cluster, and position constraints; no executor wiring |
| `autonomy/research_snapshot.py` | Polars Parquet export through SQLite `mode=ro` + `query_only`, with row/column/size/SHA-256 manifest and atomic directory cleanup |
| `autonomy/retention.py` | Fail-closed hot/cold signal retention: markets settled for seven days are eligible for a companion SQLite archive; exact count + SHA-256 verification precedes same-transaction hot deletion, while the `signal_history` union preserves full research evidence and excludes every execution/governance table |
| `autonomy/simulation_training.py` | Hourly report-only curriculum: nested settlement-lagged/event-purged forecast challengers, witnessed-fill execution filters, and event-cluster bootstrap compounding stress; read-only ledger and zero execution authority |
| `autonomy/evolution_lab.py` | Recursive report-only research evolution: evidence fingerprints, bounded genome mutation, causal/event-purged tournament replay, execution stress chamber, paired cluster bootstrap, immutable forward epochs, and trace replay; can rotate research JSON but has zero code/deployment/weight/risk/order/capital authority |
| `autonomy/crypto_paper_twin.py` | Permanent public-read-only market-horizon twin for BTC/ETH/SOL. Hourly, daily, and weekly are required coverage scopes for every asset; 15-minute remains supplemental. Every compatible nearest-expiry target is evaluated and one non-pyramiding diagnostic paper decision is frozen per asset/expiry. Unavailable listings abstain without synthetic substitution; normal positions remain fee/uncertainty/liquidity/evidence gated. The twin is independent of SHADOW/LIVE with zero broker/capital authority |
| Phantom grading (`ledger.unsettled_forecast_markets` + `reconciler.reconcile_forecast_settlements`) | Settles and grades EVERY market the machine forecasted (~1000/cycle), not just the handful it traded — one settled-markets listing per watchlist series per cycle. Calibration evidence accrues from the whole forecast surface at hundreds of settlements/day |
| `autonomy/retro.py` | Retro evidence engine for eligible targets: point-in-time replay against markets that already settled, with the market prior from historical Kalshi candlesticks and crypto spot/vol from fully closed Coinbase candles. Weather prediction replay is retired and reports `RETIRED_DATA_ONLY` |
| `autonomy/signals/market_debias.py` | Empirical price->outcome curve mined from settled-market history (the exchange's own measured miscalibration, longshot bias included). Opines only where a 5-cent price bucket has >=100 observed outcomes; the retro engine never writes retro signals for this source, so its trust weight is earned on live settlements only |
| `autonomy/forecaster.py` | Trust-scaled inverse-variance fusion with correlated-source family pooling, disagreement uncertainty, challenger quarantine, a 25% minimum crypto market anchor, and an early data-only target rejection |
| `autonomy/allocator.py` | Series-aware maker-fee EV, half-sigma uncertainty haircut, maker-first pricing, two-sided <=20c spread requirement, strict one-contract budget floor, symmetric YES/NO evaluation, crypto >=8c EV / <=75c entry guards, and rejected-candidate instrumentation |
| `autonomy/risk_brain.py` | Self-set dynamic caps: quarter-Kelly, stage ladder (SHADOW→CANARY→RAMP→CRUISE), drawdown ladder (-10% half size, -20% demote, -30% self-stop), stage close-horizon (CANARY 7d / RAMP 30d / CRUISE uncapped) so scarce early-stage slots never freeze on far-dated markets |
| `autonomy/executor.py` | Shadow book, or live through `KalshiLiveBrokerFirewallAdapter` (LIMIT only, per-order validation, transport-witnessed truth) |
| `autonomy/reconciler.py` | Cumulative/partial fill truth + settlement detection; shadow fills use public standard-book prints with captured queue depth, strict print-through, or observed quote/candle crosses; stale maker quotes expire via order-level `expiration_ts` |
| `autonomy/learner.py` | Decision-time-aligned Brier trust weights (reward = beating the contemporaneous market prior) plus the recalibration saturation guard. The Reflexion-lessons loop was removed in Wave-83 (zero callers, zero consumers) |
| `autonomy/ledger.py` | SQLite: feature-preserving signal provenance + quarantine, decisions, outcomes, settlements, trust, bankroll curve, lessons, intake-quality and execution-quality summaries |

### Ledger retention

The live ledger can accumulate millions of repeated signal observations while
open markets are monitored. Retention keeps the operational database bounded
without deleting research evidence:

```powershell
python scripts/run_dummy_ledger_retention.py
# Stop ledger-writing Dummy tasks after reviewing the dry-run, then:
python scripts/run_dummy_ledger_retention.py --apply --vacuum
```

Only `signals` rows whose market settlement is at least seven days old are
eligible. Unsettled and recently settled markets always remain hot. Apply mode
uses bounded batches and refuses a WAL-backed source because SQLite would not
guarantee an atomic cross-database commit. For every batch it copies exact row
IDs and values, verifies count and SHA-256 digest in the archive, and only then
deletes the hot copies in the same transaction. `PRAGMA integrity_check` must
pass for both databases. The archive retains a manifest for every batch.

`AutonomyLedger`, backtests, the strategy miner, tuner, loss attribution,
readiness reporting, market debiasing, retro duplicate detection, and the
simulation trainer read the connection-local `signal_history` union. Archival
therefore changes storage location, not sample history. It never touches
decisions, outcomes, settlements, source trust, bankroll, lessons, promotion
registries, risk state, orders, or capital. The command has no broker client
and reports `execution_authority=false`.

## Recursive improvement loops

1. **Calibration**: every settlement scores every source's logged signal
   (Brier vs the market-prior baseline) and updates trust multiplicatively —
   globally, per-vertical (`source@VERTICAL` rows), and at the exact
   `(source, subject, market_type, phase_or_horizon)` scope. Sparse scopes fall back to
   vertical/global trust; established scopes cannot hide behind another
   market family's record.
2. **Metabolic recalibration and repair**: every ~6h the daemon re-runs the
   backtest bootstrap, relearns exact-scope trust, refreshes contraction-only
   joint league/market/phase/regime quarantines, and refits the market-debias
   curve from the full settlement history. Quarantined cohorts abstain while
   continuing shadow grading. Expansion remains human-review-only.
   Failing sources trip a circuit breaker (quarantine + auto-retry), so an
   upstream outage degrades coverage instead of wedging the loop.
3. **Risk**: realized P&L per contract is the only currency for stage
   promotion; drawdown demotes instantly with a 24h cooloff.
4. **Reflexion — removed (Wave-83)**: the LLM lesson-distillation loop had
   zero callers and zero consumers (see the `autonomy/learner.py` module
   docstring). The ledger `lessons` table remains for any future scope that
   earns a real producer AND consumer.
5. **Rejection classification (truth layer, not a feedback loop)**: broker
   rejections are classified (`kalshi/rejection_classifier.py`) only by the
   second-proof truth layer (`core/second_proof_runner.py`,
   `core/second_proof_intake.py`) to separate genuine broker rejections from
   local gate blocks in evidence reports. Nothing feeds the categories back
   into decision filters.
6. **Simulation curriculum**: an hourly read-only champion/challenger run
   rejects weak forecast, execution, and compounding policies before they
   consume scarce shadow fills. Simulated results are quarantined from canary
   and scale evidence and can only propose a later bounded shadow experiment.

## Four-model OpenRouter research panel

The current directed panel is an exact, role-diverse set:

| Provider model | Bounded role calls |
|---|---|
| `google/gemini-3.6-flash` | Supplied-data extraction and the primary probability pass |
| `openai/gpt-5.6-luna` | Independent low-latency structured forecast with a research-only trade draft |
| `anthropic/claude-sonnet-5` | Deep strategy critique and market-thesis synthesis |
| `z-ai/glm-5.2` | Adversarial no-trade gate, risk/hypothesis falsification, and calibration critique |

`HybridForecastEngine.hybrid_review` makes seven independent, statically
routed calls: primary forecast, rapid forecast/trade draft, no-trade review,
strategy critique, risk critique, thesis, and calibration. No model receives
another model's response. The batch is atomic and fail-closed: a missing,
extra, duplicated, misrouted, wrong-model, mock/fallback, timed-out, or
semantically malformed envelope invalidates the entire model review. The
quantitative forecast, confidence, uncertainty band, vetoes, and no-trade
decision then remain unchanged.

The provider/model set is exact and order-independent. Archived providers may
remain configured for historical tests or diagnostics, but they cannot join
the production panel. The current evidence lineage is
`openrouter_gemini36flash_gpt56luna_claudesonnet5_glm52_v1`; evidence produced
by the retired Gemini 3.5 Flash / GPT-5.6 Terra pair, or by any interim panel,
has zero authority under this lineage and cannot be relabeled or pooled into
it.

Successful calls are research observations, not permission to move a
probability or trade. Model probability weight defaults to zero. It can become
nonzero only through an explicit exact-scope promotion dossier bound by
SHA-256 to fresh (at most seven days old), point-in-time,
receipt-bounded forward settlement evidence from all four exact models, with
no retro rows, at least 300 unique independent event clusters, and a positive
95% lower confidence bound on Brier edge. Even then, the earned model weight
is capped at 0.35; missing, stale, cross-scope, duplicated, tampered, demoted,
or self-promoting evidence resolves to zero authority.

Model access and order submission are separate controls. The shipped routing
configuration keeps `live_model_calls_enabled=false`; the debate runtime flag
alone cannot override that gate. Live order submission also remains disabled,
and enabling research model calls would not grant order, risk, probability,
promotion, or capital authority. With model calls off, mock votes are ignored
and the loop remains pure-quant. See
`docs/OPENROUTER_FOUR_MODEL_PANEL_2026-07-22.md` for the current panel contract.

Provider networking is also enforced at the lower-level sinks. Real provider
adapters require a process-local capability minted only after the router's
strict checked gate; the legacy resolver is preflight-only unless it receives
both literal `allow_live=True` and the same capability. Provider endpoints are
HTTPS host-allowlisted and bound to their intended credential, alias probes are
bounded, and archived V8 report generators are zero-network by default.
Opening dashboards or running ordinary pytest therefore cannot inherit the
project `.env` credential and silently create paid calls.

Every production order request carries an immutable model-influence
attestation. `QUANT_ONLY` binds zero model authority; `MODEL_WEIGHTED` binds the
exact forecast, proposal, model-output reference, scope, evidence artifact,
and earned weight. The central firewall rejects omission or tampering and
independently re-evaluates the current exact scope before submit. Crypto scopes
are separate for `15m`, `1h`, `1d`, and `1w`; sports scopes are separate for
pre-game and live/in-play evidence. An authorized panel abstention is a hard
veto, while mock/fallback/zero-authority text remains non-operational.

Exit decisions follow the same proof boundary: the brain publishes
`runtime/autonomy/exit_advisories.json`, marked at the displayed bid and net of
taker fees. A displayed bid is not called a fill: quote freshness, displayed
depth, entry-cost provenance, active-entry state, mark change, and time to close
are recorded separately. It is explicitly `shadow_advisory_only`; it cannot
place a sell.

`python scripts/run_dummy_exit_policy_evaluator.py` joins only point-in-time v2
advisories to witnessed fills and verified settlement P&L. It evaluates the
first trigger for fixed model-value, adverse-selection, stop-loss, take-profit,
and time-exit challengers under 0/1/3/5-cent slippage and event-cluster
bootstrap intervals. Passing that research gate still grants no execution or
capital authority; sell submission and partial-fill reconciliation require
separate firewall-backed proof and explicit operator authorization.

## Pre-live checklist (bootstrapping calibration)

```bash
# Optional contextual-data QA only; never creates eligible forecasts/orders:
python scripts/run_dummy_weather_backfill.py
python scripts/run_dummy_sports_warmup.py --league mlb  # warm Elo (done: 590 games)
python scripts/run_dummy_sports_warmup.py --league nfl  # NFL preseason (KXNFLGAME live from Aug)
python scripts/run_dummy_autonomous.py start            # shadow — accumulate settlements
# Evidence accrues two ways, both honest:
#  - phantom grading: every forecasted market is graded when it settles
#    (runs inside every cycle automatically)
#  - retro replay: grade the recent PAST with point-in-time reconstruction
python scripts/run_dummy_retro_backfill.py --bootstrap  # replay history + weights + gate report
python scripts/run_dummy_backtest.py --bootstrap        # re-grade any time
python scripts/run_dummy_backtest.py --summary          # compact uncertainty/intake/execution readout
python scripts/run_dummy_autonomous.py canary            # retired paper audit report (no live authority)
python scripts/run_dummy_autonomous.py status           # review weights + ROI, then go live
python scripts/ingest_dummy_public_statistics.py        # public reads -> raw local facts
python scripts/export_dummy_research_snapshot.py        # reproducible read-only corpus
python scripts/run_dummy_portfolio_challenger.py --budget-cents 500 --max-positions 8 --max-group-cost-cents 150
python scripts/run_dummy_simulation_training.py --summary  # read-only hourly curriculum
powershell -ExecutionPolicy Bypass -File scripts/install_simulation_training_task.ps1
```

Crypto hardening evidence and challenger gates are documented in
`docs/CRYPTO_PERFORMANCE_AUDIT.md`.

## Dummy doctrine

- Fail closed with honest status enums (`CYCLE_OK`, `HALTED_KILL_SWITCH`,
  `HALTED_SELF_STOP:*`, `CYCLE_DEGRADED_*`); gates may only be added or
  hardened.
- Source trust is earned from realized outcomes only; untrusted evidence is
  quarantined and never promoted.

## Safety invariants (unchanged by autonomy)

- Every live order goes through the hardened adapter: LIMIT only, price 1-99,
  idempotency key required, per-order notional from the risk brain.
- Live sessions expire; the executor re-validates session + kill switch at
  the moment of every submit.
- Broker contact is claimed only on transport witness.
- `stop` (or the -30% drawdown ladder) halts everything unconditionally.
