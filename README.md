# Dummy

Private, evidence-gated prediction-market intelligence for crypto and sports.
Dummy collects point-in-time public evidence, calibrates competing forecasts,
simulates and stress-tests challengers, explains every paper decision, and
records the full lifecycle in an auditable ledger.

- **Crypto arsenal:** BTC, ETH, and SOL across native 15-minute, hourly, daily,
  and weekly horizons, combining realized and implied volatility, market
  regime, momentum, technical, volume, order-book, and cross-venue evidence.
- **Sports arsenal:** MLB winners, totals, and YRFI/NRFI; UFC winners, round
  totals, and distance; NBA, NCAAB, NFL, NCAAF, and NHL winners and totals;
  plus Formula One race-winner modeling.
- **Training arsenal:** point-in-time replay, Monte Carlo simulation,
  adversarial arenas, event-purged walk-forward validation, calibration and
  risk analytics, deterministic replay buffers, and bounded recursive
  challenger evolution.

Live execution remains fail-closed, evidence-gated, and subject to explicit
operator authorization.

## Current paper operation

The market-horizon paper twin runs every five minutes through the Windows
`DummyCryptoPaperTwin` scheduled task. It continuously scans public Kalshi
markets for BTC, ETH, and SOL at native 15-minute, hourly, daily, and weekly
horizons, plus daily and weekly WTI, natural-gas, and gold cohorts. Each cycle
records the point-in-time market state, target selection, probability, policy
gates, simulated fill evidence, settlement, and a plain-language decision
explanation in the local audit ledger and report artifacts.

This is live **paper** operation only: it has no credentials, broker contact,
execution authority, or capital authority. It remains active while clean
forward evidence accumulates. Promotion is a separate, explicit review gated
by settled out-of-sample calibration, event-cluster robustness, witnessed-fill
performance after fees and slippage, drawdown limits, and the canary firewall.
Elapsed runtime, backtests, or counterfactual quote P&L cannot promote it.

The local command-center dashboard at `http://127.0.0.1:8787/` tracks scheduler
health, active and settled paper trades, decision explanations, lane-level
calibration and P&L, target-evidence progress, weaknesses, and promotion gates.
Its Start and Stop controls only enable or pause `DummyCryptoPaperTwin`; they
cannot reach live execution, credentials, risk settings, or capital.

![Dummy paper trading command center](docs/assets/dummy-paper-dashboard.jpg)

## The loop

```
scan → signal → fuse → allocate → risk → execute → reconcile → learn
```

Every cycle (10-minute cadence via a scheduled task) the predator sweeps the
watchlist series, prices every market with every applicable source, fuses
opinions by earned trust, ranks opportunities by capital velocity
(edge per √hour-to-settlement), sizes with quarter-Kelly under a stage
ladder, places maker-first LIMIT orders in the active book (shadow by
default), reconciles settlements, and grades every source against reality.

## Recursive improvement

- **Calibration**: every settlement Brier-scores every source that opined —
  globally and per-vertical (`source@VERTICAL`) — and updates trust
  multiplicatively. Influence is earned by beating the market, nothing else.
- **Contested truth**: trust and the live gate key on the *contested* record
  (markets where a source disagreed with the market prior by ≥5¢ — the
  population it would actually trade). Agreeing with the market and being
  right proves nothing.
- **Phantom grading**: every forecasted market (~1,000/cycle) is settled and
  graded when it closes, not just the handful traded — evidence accrues at
  hundreds of settlements per day.
- **Retro replay**: point-in-time reconstruction against already-settled
  markets (historical candles + historical forecasts + contemporaneous
  market quotes from candlesticks), no lookahead.
- **Metabolic recalibration**: every ~6h the daemon re-runs the backtest
  bootstrap and refits the debias curve. No operator in the loop.
- **Model evolution**: challengers run beside champions under their own
  source names and earn their way in or starve.
- **Crypto correlation control**: Coinbase flat-vol and EWMA-tail models are
  one evidence family, not two independent votes; crypto retains a 25% market
  anchor and challengers remain excluded until explicit promotion review.
- **Simulation training**: an hourly read-only curriculum searches
  shrinkage/edge/uncertainty policies with settlement-lagged, event-purged
  walk-forward tests; separately trains witnessed-fill execution filters and
  cluster-bootstrap compounding stress. It can propose a bounded shadow
  experiment but cannot change weights, risk, readiness, or orders.
- **Always-on market-horizon paper twin**: every five minutes, the exact crypto
  universe (BTC/ETH/SOL at native 15m, hourly, daily, and weekly horizons) and
  WTI/natural-gas/gold daily/weekly cohorts run isolated incumbent, recursive,
  and exploratory lanes. Unlisted horizons abstain explicitly; listed markets
  explain every decision, simulate one-contract top-ask entries, and diagnose
  maker execution from public prints. It runs beside shadow and authorized live
  sessions but has no credentials, broker, readiness, execution, or capital authority.
- **Multi-sport game engine**: MLB, NFL, NCAAF, NHL, NBA, NCAAB, UFC, and F1
  challengers feed a deterministic replay buffer and Monte Carlo curriculum.
  League-isolated genomes progress through Rookie/Veteran/Elite/Boss tiers,
  face fog-of-war/meta-shift/boss-chaos arenas, and unlock mutation skills only
  after settled event-cluster evidence. Deep analytics include Brier, log loss,
  ECE/MCE, AUC, sharpness, Sortino, drawdown, and paired-cluster confidence.
  Research champions cannot rewrite code, alter production weights, or trade.
- **Reflexion**: losing decisions distilled into structured lessons via the
  model router.

## Success measurement and execution truth

- Source trust is graded at the **earliest decision timestamp** for traded
  markets, or the earliest recorded opinion for phantom-only markets. Later
  near-settlement quotes cannot rewrite the evidence that produced a trade.
- A shadow maker order is pending until a public standard-book trade consumes
  its captured queue, prints strictly through its limit, or a later quote/
  one-minute candle proves a cross. Uncrossed orders expire on the same
  1-minute crypto / 45-minute other-market TTL as live orders and never create
  positions or P&L. Fixed-point dollar books are normalized explicitly.
- Accepted live orders reserve risk, but settlement P&L uses only the broker's
  witnessed cumulative `fill_count`. Partial fills survive cancellation as
  real positions; unfilled orders settle with zero P&L.
- Allocation uses the current series-aware maker-fee schedule plus a
  half-sigma probability haircut. If the embedded fee schedule is older than
  31 days, maker estimates fail closed to the higher taker fee.
- `run_dummy_backtest.py` reports verified realized P&L, fill quality, final
  ensemble Brier/log loss versus the contemporaneous market, and one-snapshot-
  per-market edge-threshold diagnostics. Counterfactual midpoint results are
  explicitly separated from fill-adjusted realized performance.
- Backtest uncertainty is event-cluster aware: adjacent strikes for the same
  expiry are resampled together instead of pretending every contract is an
  independent observation. Reports include 95% Brier/log-loss advantage
  intervals, ECE/MCE calibration, strict chronological stability folds, and
  point-in-time walk-forward threshold selection that only trains on outcomes
  settled before the next test window.
- Signal intake persists the exact feature payload and receipt timestamp.
  Non-finite/range-invalid probabilities, malformed feature JSON, future
  timestamps, and duplicate signal grains are quarantined and surfaced in the
  dashboard instead of entering calibration.
- Allocation requires a two-sided book with a spread no wider than 20¢ and
  refuses an order when remaining budget cannot buy one contract or more than
  50 contracts are already queued at its price. Shadow and live share these
  execution filters. Shadow equity and drawdown use verified settled-fill P&L,
  not a fixed paper balance.
- Raw public statistics are kept in a separate deduplicated observation table
  with series, observation/publish/receipt times, units, and feature payloads.
  BLS macro releases, Deribit BTC/ETH DVOL, and official NWS station readings
  cannot influence forecasts until a settlement-backed transformation exists.
- River ADWIN monitors chronological Brier excess for statistically unusual
  degradation. It is diagnostic only; confirmed negative drift blocks scale
  readiness rather than silently changing weights.
- OR-Tools produces a report-only discrete portfolio challenger, and Polars
  exports hash-manifested Parquet research snapshots through a query-only
  SQLite connection. Neither path has execution authority.

## Self-managed risk

- Quarter-Kelly sizing under a stage ladder (SHADOW → CANARY → RAMP →
  CRUISE); promotion strictly on realized settled P&L, demotion instant.
- Drawdown ladder: −10% half size, −20% demote, −30% hard self-stop.
- Correlation clustering: adjacent strikes / city-days / both game sides
  collapse into one cluster with its own caps.
- Stage close-horizon: early stages only hold near-dated markets so
  position slots recycle.
- Exchange-enforced order TTL (1min crypto / 45min elsewhere) instead of
  cancel loops.

## Safety invariants

- **Evidence gate**: a LIVE canary refuses to start until ≥20 settled markets,
  ≥100 settled decision snapshots across ≥20 event clusters, a positive
  cluster-robust Brier advantage, ≤8% calibration error, ≥100 profitable
  point-in-time walk-forward trades, bootstrapped weights, one statistically
  positive contested source, five witnessed shadow fills, five settled fills
  with positive verified P&L, and positive fill-conditioned Brier skill exist.
- **Canary is not scale**: scale readiness is reported separately and remains
  blocked until at least 20 witnessed fills have settled with positive verified
  net P&L. Counterfactual performance can authorize a tiny experiment, never a
  capital ramp.
- Live orders go through a hardened firewall adapter: LIMIT only,
  per-order validation, transport-witnessed truth (broker contact is
  claimed only on HTTP evidence).
- Maintenance awareness: exchange down → cycle skips cleanly; trading
  paused → learning continues, zero orders.
- Circuit breakers quarantine failing sources; errors are eaten as
  evidence, never stalls.
- The kill file stops everything, instantly and unconditionally.

## Operator surface

The evaluated open-source expansion backlog and licensing boundaries are in
[`docs/OPEN_SOURCE_OPPORTUNITY_AUDIT.md`](docs/OPEN_SOURCE_OPPORTUNITY_AUDIT.md).

```bash
python scripts/run_dummy_autonomous.py start          # shadow session
python scripts/run_dummy_autonomous.py canary --live  # evidence gate + balance
python scripts/run_dummy_autonomous.py start --live --ack "<exact ack>"
python scripts/run_dummy_autonomous.py stop           # instant, unconditional
python scripts/run_dummy_dashboard.py --port 8787     # read-only dashboard
python scripts/run_dummy_retro_backfill.py --bootstrap
python scripts/ingest_dummy_public_statistics.py       # public facts, local ledger only
python scripts/export_dummy_research_snapshot.py       # SQLite mode=ro -> Parquet
python scripts/run_dummy_portfolio_challenger.py --budget-cents 500 --max-positions 8 --max-group-cost-cents 150
python scripts/run_dummy_simulation_training.py --summary   # report-only, ledger mode=ro
powershell -ExecutionPolicy Bypass -File scripts/install_simulation_training_task.ps1
python scripts/run_dummy_crypto_paper_twin.py --summary
powershell -ExecutionPolicy Bypass -File scripts/install_crypto_paper_twin_task.ps1
Get-ScheduledTaskInfo -TaskName DummyCryptoPaperTwin
```

The hourly trainer also runs the quarantined recursive evolution lab. It
mutates bounded research genomes, replays them causally, stress-tests degraded
execution, and accumulates later forward evidence without changing production
code, weights, risk, orders, or capital. See `docs/EVOLUTION_LAB.md`.

Details: [docs/AUTONOMY.md](docs/AUTONOMY.md).
Training protocol: [docs/SIMULATION_TRAINING_REGIMEN.md](docs/SIMULATION_TRAINING_REGIMEN.md).
Crypto audit: [docs/CRYPTO_PERFORMANCE_AUDIT.md](docs/CRYPTO_PERFORMANCE_AUDIT.md).
Crypto paper twin: [docs/CRYPTO_PAPER_TWIN.md](docs/CRYPTO_PAPER_TWIN.md).
