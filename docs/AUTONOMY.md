# Dummy Autonomy Layer

Shipped 2026-07-08. The predator loop: scan → signal → forecast → allocate →
risk → execute → reconcile → learn. Operator surface is start/stop only;
everything between is decided by the system inside the risk brain's survival
constraints.

## Operator dashboard + alerts

```bash
python scripts/run_dummy_dashboard.py --port 8787   # open http://127.0.0.1:8787/
```

Read-only page: liveness/heartbeat, live-canary gate + blockers, risk state,
per-source calibration scoreboard, recent cycles, bankroll curve, and alerts.
Alerts (`autonomy/alerts.py`) fire once per episode on SELF_STOP, drawdown
ladder deepening, evidence-gate-green, and cycle-error streaks — written to
`runtime/autonomy/alerts.jsonl` and surfaced on the dashboard.

Two API surfaces:

- `GET /api/status` — fast precomputed snapshot. Reads only the fresh runtime
  JSON artifacts plus `watchdog_status.json`; it NEVER opens `ledger.db`.
  Every panel payload carries `data_ages` (per-artifact timestamp, age in
  seconds, cadence-derived threshold, `stale` flag) so stale data is visibly
  stale instead of rendering as healthy.
- `GET /api/autonomy` — the full evidence report (includes a 1,000-resample
  cluster bootstrap over the ledger). It is cached for 30 s and computed on a
  background worker with a bounded request deadline
  (`DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS`, default 20 s). A cold request
  that misses the deadline gets the last cached value marked
  `stale_cache: true`, or a `503` pointing at `/api/status` when no cache
  exists yet — it no longer blocks for minutes recomputing the bootstrap
  inline. The dashboard UI falls back to `/api/status` automatically.

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
| DummyMispricingMonitor | mispricing_monitor_latest.json (`generated_at`) | 2 min | 4 min |
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
timestamp refuses the order. A LIVE submit additionally re-checks the venue
halt state (`/exchange/status`) at the moment of submit, not just at cycle
start; a status-fetch failure fails open (unknown is not down), matching the
cycle-start doctrine.

## Continuous shadow + going live (Tier 1)

```bash
# Continuous shadow (durable): register the scheduled task ONCE, elevated.
scripts\install_shadow_task.bat        # 10-min cycles, survives reboot
# ...or run the loop yourself:
python scripts/run_dummy_shadow_daemon.py --loop --interval 600

# Watch liveness + history:
type runtime\autonomy\heartbeat.json
type runtime\autonomy\cycles.jsonl

# When settlements have accrued, grade + pre-rank, then check readiness:
python scripts/run_dummy_backtest.py --bootstrap
python scripts/run_dummy_autonomous.py canary        # evidence gate report

# First live canary — BLOCKED until the gate passes: >=20 settled markets,
# bootstrapped weights, five verified settled fills with positive P&L and
# fill-conditioned Brier skill, and at least one CONTESTED market-beating
# record (>=20 settled markets where it disagreed with the market prior by
# >=5c AND was right more than 55% of the time). Agreeing with the market and
# being right qualifies nothing. Enable the LLM panel for the session with the
# env var. This is the one irreversible step; it's yours.
set DUMMY_DEBATE_LIVE=1
python scripts/run_dummy_autonomous.py start --live --hours 6 --ack "<exact ack>"

# Stop everything, instantly:
python scripts/run_dummy_autonomous.py stop
```

The evidence gate (`autonomy/canary.py`) is fail-closed: a LIVE start returns
`started: false` with exact blockers until the shadow record proves earned
calibration. `--override-evidence-gate` exists but is deliberate operator
intent only.

## Commands

```bash
# Shadow session (default): full pipeline on live public data, orders recorded
# in the shadow book only. This is the calibration bootstrap — run it early,
# run it often.
python scripts/run_dummy_autonomous.py start

# One cycle (cron-able):
python scripts/run_dummy_autonomous.py once

# Status (session, kill switch, performance summary, risk state):
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
human-only: the `AutoPromotionEngine` (`autonomy/auto_promotion.py`, run daily
inside the readiness task by `autonomy/auto_promotion_runner.py`) promotes a
scope into fusion when it clears a two-stage evidence ladder including a
fee-adjusted counterfactual **proof of profit** — see
`docs/AUTO_PROMOTION.md` for every threshold, rail, and the full rationale.
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
| `autonomy/scanner.py` | Series-targeted sweep of live Kalshi markets (watchlist of weather cities + crypto ladders); normalizes the dollars-string field schema |
| `autonomy/signals/weather_openmeteo.py` | Multi-model Open-Meteo ensemble (GFS/ECMWF/ICON) vs KXHIGH* temperature strikes; metadata-driven strike semantics with integer-reading continuity corrections |
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
| `autonomy/debate.py` | Five-model LLM panel (distinct providers × temperatures) with a revision round; adjudicates only the top-K edge markets per cycle, injected as a trust-weighted signal |
| `autonomy/weather_calibration.py` | Historical-forecast backfill: per-city bias + sigma from past Open-Meteo forecasts vs ERA5 actuals, pre-training the weather signal |
| `autonomy/signals/commodities_spot.py` | WTI/natgas/gold spot + realized vol (keyless Yahoo Finance) → lognormal strike probabilities for KXWTI/KXNATGAS/KXGOLD |
| `autonomy/correlation.py` + risk brain group caps | Collapses correlated markets (adjacent strike buckets, one city-day, both game sides) into one cluster; per-cluster exposure + position-count caps stop the bankroll piling onto one underlying |
| `autonomy/backtest.py` | Leakage-resistant replay: decision-time source grading, ECE/MCE, event-cluster bootstrap confidence intervals, strict chronological stability folds, point-in-time walk-forward threshold selection, verified realized P&L/drawdown/profit factor, fill analytics, and derived trust weights |
| `autonomy/drift.py` | River ADWIN diagnostic over ordered Brier excess; reports local negative regime shifts and can block scale, but never changes weights or orders |
| `autonomy/statistics_intake.py` | Public BLS macro, Deribit DVOL, and NWS station observations stored as deduplicated raw facts with timestamps, units, and provenance; no probability conversion |
| `autonomy/portfolio_challenger.py` | OR-Tools CP-SAT report-only candidate selection with budget, payout sanity, event-cluster, and position constraints; no executor wiring |
| `autonomy/research_snapshot.py` | Polars Parquet export through SQLite `mode=ro` + `query_only`, with row/column/size/SHA-256 manifest and atomic directory cleanup |
| `autonomy/retention.py` | Fail-closed hot/cold signal retention: markets settled for seven days are eligible for a companion SQLite archive; exact count + SHA-256 verification precedes same-transaction hot deletion, while the `signal_history` union preserves full research evidence and excludes every execution/governance table |
| `autonomy/simulation_training.py` | Hourly report-only curriculum: nested settlement-lagged/event-purged forecast challengers, witnessed-fill execution filters, and event-cluster bootstrap compounding stress; read-only ledger and zero execution authority |
| `autonomy/evolution_lab.py` | Recursive report-only research evolution: evidence fingerprints, bounded genome mutation, causal/event-purged tournament replay, execution stress chamber, paired cluster bootstrap, immutable forward epochs, and trace replay; can rotate research JSON but has zero code/deployment/weight/risk/order/capital authority |
| `autonomy/crypto_paper_twin.py` | Permanent public-read-only market-horizon twin: exact BTC/ETH/SOL 15m/hourly/daily/weekly allowlist plus vertically isolated WTI/natural-gas/gold daily/weekly cohorts; unavailable listings abstain explicitly; immutable explanations, one position per vertical/asset/expiry/lane, quote-executable taker simulation, public-print maker diagnostics, frozen epochs, paper-canary gates, and stress-only compounding proposals; independent of SHADOW/LIVE and zero broker/capital authority |
| Phantom grading (`ledger.unsettled_forecast_markets` + `reconciler.reconcile_forecast_settlements`) | Settles and grades EVERY market the machine forecasted (~1000/cycle), not just the handful it traded — one settled-markets listing per watchlist series per cycle. Calibration evidence accrues from the whole forecast surface at hundreds of settlements/day |
| `autonomy/retro.py` | Retro evidence engine: point-in-time replay against markets that already settled. Market prior from Kalshi candlesticks at the historical decision moment; crypto spot/vol from historical Coinbase candles fully closed before it; weather from the Open-Meteo historical-forecast API (the day's own model runs). Signals land in the ledger as `mode='retro'` with historical timestamps; fail-closed (no contemporaneous quote -> market skipped) |
| `autonomy/signals/market_debias.py` | Empirical price->outcome curve mined from settled-market history (the exchange's own measured miscalibration, longshot bias included). Opines only where a 5-cent price bucket has >=100 observed outcomes; the retro engine never writes retro signals for this source, so its trust weight is earned on live settlements only |
| `autonomy/forecaster.py` | Trust-scaled inverse-variance fusion with correlated-source family pooling, disagreement uncertainty, challenger quarantine, and a 25% minimum crypto market anchor |
| `autonomy/allocator.py` | Series-aware maker-fee EV, half-sigma uncertainty haircut, maker-first pricing, two-sided <=20c spread requirement, strict one-contract budget floor, symmetric YES/NO evaluation, crypto >=8c EV / <=75c entry guards, and rejected-candidate instrumentation |
| `autonomy/risk_brain.py` | Self-set dynamic caps: quarter-Kelly, stage ladder (SHADOW→CANARY→RAMP→CRUISE), drawdown ladder (-10% half size, -20% demote, -30% self-stop), stage close-horizon (CANARY 7d / RAMP 30d / CRUISE uncapped) so scarce early-stage slots never freeze on far-dated markets |
| `autonomy/executor.py` | Shadow book, or live through `KalshiLiveBrokerFirewallAdapter` (LIMIT only, per-order validation, transport-witnessed truth) |
| `autonomy/reconciler.py` | Cumulative/partial fill truth + settlement detection; shadow fills use public standard-book prints with captured queue depth, strict print-through, or observed quote/candle crosses; stale maker quotes expire via order-level `expiration_ts` |
| `autonomy/learner.py` | Decision-time-aligned Brier trust weights (reward = beating the contemporaneous market prior), Reflexion lessons via ModelRouter |
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
4. **Reflexion**: losing decisions are periodically distilled into structured
   lessons through the model router and stored in the ledger.
5. **Rejection avoidance**: broker rejections carry classifier categories
   (kalshi/rejection_classifier.py) back into decision filters.
6. **Simulation curriculum**: an hourly read-only champion/challenger run
   rejects weak forecast, execution, and compounding policies before they
   consume scarce shadow fills. Simulated results are quarantined from canary
   and scale evidence and can only propose a later bounded shadow experiment.

## Enabling the LLM debate panel

The five-model panel is wired but gated off by cost control. To activate:

1. Set `live_model_calls_enabled: true` in `configs/model_routing.json`.
2. Ensure `OPENROUTER_API_KEY` is set (it is, in `.env`).

The panel then adjudicates the top-5 edge markets each cycle using five
distinct models — deepseek-v3, minimax-01, llama-3.3-70b, gemini-2.0-flash,
qwen-2.5-72b — each estimating a probability, then a revision round where each
sees the others' numbers. Result is injected as one `llm_debate` signal and
graded by the calibration ledger like any source. With live calls off (the
default), the panel returns cleanly with no effect (mock votes are ignored),
so the loop runs pure-quant.

Add or swap panel models by editing `provider_configs` in the routing config —
any `route_mode: "openrouter"` entry is picked up automatically (no code
change), courtesy of the generic `OpenRouterProvider`.

## Pre-live checklist (bootstrapping calibration)

```bash
python scripts/run_dummy_weather_backfill.py            # pre-train weather (done: 8 cities)
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
python scripts/run_dummy_autonomous.py canary            # statistically hardened tiny-live gate
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
