# Dummy

Private, evidence-gated prediction-market intelligence for crypto and sports.
Dummy collects point-in-time public evidence, calibrates competing forecasts,
simulates and stress-tests challengers, explains every paper decision, and
records the full lifecycle in an auditable ledger.

- **Crypto arsenal:** BTC, ETH, and SOL across native 15-minute, hourly, daily,
  and weekly horizons, combining realized and implied volatility, market and
  macro risk regime (S&P/DXY/VIX/10y/gold/oil), momentum, technical, volume,
  order-book, and cross-venue evidence.
- **Sports arsenal:** MLB winners, totals, spreads, and YRFI/NRFI — with real
  left/right platoon splits, per-team bullpen quality, rivalry/divisional
  awareness, probabilistic baserunning, and a gated StatsAPI plate-appearance
  simulator for confirmed live lineups and starters; NBA, NCAAB, NFL, NCAAF,
  and NHL winner/spread/total markets, each priced by a league-specific pregame
  and live kernel and cross-checked by a power-ratings ensemble challenger
  (ESPN FPI/BPI, in-house Elo, and in-house Massey and tie-aware Colley ratings
  computed from public final scores). NFL and NCAAF overtime is possession-aware
  and fail-closed without ESPN drive state, while NHL uses a
  positive-shared-component bivariate Poisson.
  (UFC and Formula One retired 2026-07-12.)
- **Training arsenal:** point-in-time replay, Monte Carlo simulation,
  adversarial arenas, event-purged walk-forward validation, calibration and
  risk analytics, deterministic replay buffers, and bounded recursive
  challenger evolution.

Live execution remains fail-closed, evidence-gated, and subject to explicit
operator authorization.

## vNext: sovereign forecasting architecture

Dummy's next architecture is a deterministic, typed forecasting ecology:
market-specific agent organisms consume versioned world state, generate
competing futures, challenge one another, estimate their knowledge boundary,
and either issue a fully replayable forecast or abstain. The system may evolve
research components, but it may never evolve its truth rules, promotion
standards, credential boundaries, execution firewall, or operator authority.

The implementation is an adapter-first migration—not a rewrite of proven
specialists—and every new subsystem starts as
`EXPERIMENTAL_SOVEREIGN_FORECASTING`. The reviewed architecture, staged
delivery plan, benchmark claims, and exit gates are documented in
[`docs/VNEXT_MASTER_PLAN_INTEGRATION.md`](docs/VNEXT_MASTER_PLAN_INTEGRATION.md).
Phase 0/1 now has a frozen
[`evidence baseline`](docs/VNEXT_PHASE0_BASELINE.json), a reviewed
[`governance audit`](docs/VNEXT_PHASE0_GOVERNANCE_AUDIT.md), and an executable
[`protected-surface manifest`](docs/VNEXT_PROTECTED_SURFACES.json). These add no
execution authority; current canary and scale gates remain blocked by the
recorded operational evidence.

Phase 2 adds the inactive, research-only
[`agent control plane`](docs/VNEXT_PHASE2_AGENTIZATION.md) and its canonical
[`contract catalog`](docs/VNEXT_PHASE2_CONTRACT_CATALOG.json): versioned
contracts, lifecycle, health, permissions, deterministic mailbox/runtime, and
read-only incumbent adapters. Phase 3 adds the first deterministic,
[`shadow-only forecast organism`](docs/VNEXT_PHASE3_ORGANISM.md) and compact
[`template catalog`](docs/VNEXT_PHASE3_TEMPLATE_CATALOG.json) for native BTC
15-minute direction and MLB pregame winner markets. Each episode freezes
point-in-time evidence, generates and attacks competing futures, emits a typed
forecast or abstention, simulates witnessed-depth paper execution, settles and
grades every role, replays bounded proposals on distinct held-out clusters,
and then dissolves. It cannot substitute for the incumbent or modify weights,
orders, promotion, or capital.

Phase 4 adds the immutable
[`horizon- and league-specific world model`](docs/VNEXT_PHASE4_WORLD_MODELS.md)
and its canonical [`schema catalog`](docs/VNEXT_PHASE4_WORLD_MODEL_SCHEMAS.json).
Every fact, derived value, hypothesis, contradiction, and missing value carries
typed uncertainty and provenance. Critical state is lease-bound and fails
closed when stale or incoherent; every organism role propagates the same frozen
content version. Current [`ablation`](docs/VNEXT_PHASE4_WORLD_STATE_ABLATION.json)
and [`regime-transfer`](docs/VNEXT_PHASE4_REGIME_TRANSFER.json) artifacts
honestly report insufficient settled evidence, so they make no performance or
readiness claim.

Phase 5 adds the [`contraction-only shadow, structured synthesis, and
metacognitive control layer`](docs/VNEXT_PHASE5_METACOGNITION.md). Eight guards
can only downgrade, request evidence, quarantine, veto, abstain, or terminate;
family-aware synthesis preserves a reviewed 0.50 market-prior floor and gives
stale evidence zero weight. Confidence is decomposed into 12 independently
auditable components, while unknown compute remains unknown and blocks a
marginal-utility claim. The checked-in
[`abstention`](docs/VNEXT_PHASE5_ABSTENTION_VALUE.json),
[`resource-efficiency`](docs/VNEXT_PHASE5_RESOURCE_EFFICIENCY.json), and
[`meta-calibration`](docs/VNEXT_PHASE5_METACOGNITION_CALIBRATION.json) reports
honestly contain no settled cases, so Phase 5 remains shadow-only with its
empirical evidence gates pending.

Phase 6 adds the [`layered causal memory, forecast-genome, and bounded recursive
evolution system`](docs/VNEXT_PHASE6_MEMORY_EVOLUTION.md). Immutable observation,
episode, settlement, fill, failure, calibration, strategy, theory, and genome
records form a tamper-evident causal ledger. Generation-zero BTC 15-minute and
MLB pregame genomes may produce proposal-only research descendants across six
recursive levels, but the constitutional manifest prevents mutations from
reaching truth, evidence, evaluation, promotion, credential, or execution
surfaces. Candidate families are judged externally using purged held-out event
clusters, clustered intervals, Holm-Bonferroni correction, and transfer tests.
The checked-in [`evolution evidence`](docs/VNEXT_PHASE6_EVOLUTION_EVIDENCE.json)
contains zero genuine settled candidates and reports
`INSUFFICIENT_SETTLED_EVIDENCE`; no source edit, runtime application,
performance claim, automatic promotion, or execution authority is granted.

Phase 7 adds the [`read-only intelligence observatory, adversarial arenas, and
homeostasis controller`](docs/VNEXT_PHASE7_OBSERVATORY_ARENAS.md). The
observatory projects command-center, organism, world-model, calibration,
execution-truth, evolution, health, and constitutional state with an evidence
link for every claim. The complete 40-scenario arena catalog covers forecast,
sports, crypto, and metacognitive failure modes; all checked-in fixture replays
are deterministic. Nineteen health variables can produce contraction-only or
proposal-only interventions that never increase authority. The current
[`observatory snapshot`](docs/VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json) explicitly
contains no live vNext telemetry, and the arena report contains zero runtime
episodes, so these artifacts prove mechanics and governance—not empirical
resilience or production readiness.

Phase 8 adds the protected [`benchmark, claim-by-claim evidence, and human-only
promotion review program`](docs/VNEXT_PHASE8_CLAIMS_PROMOTION.md). Its 32-metric
catalog covers forecast, multi-agent, metacognitive, execution, evolution, and
governance quality. The current review supports zero performance claims,
records two governance-only findings, and marks six claims as
`INSUFFICIENT_EVIDENCE`; material improvement is not established. The aggregate
remains `SHADOW_ONLY`, with 12 of 13 promotion evidence gates unsatisfied.
Promotion is blocked, unrequested, human-only, and unapplied.

The protected [`nested forecast autoresearch loop`](docs/VNEXT_AUTORESEARCH.md)
extends Phase 6 with a separate outer evolution researcher and inner forecast
research organism. Sealed visible/private/external task partitions, aggregate-
only private receipts, lineage-bandit search, stall-triggered champion forks,
role-specific context compression, eight reward-hacking canaries, complexity
Pareto pressure, semantic minimization, and a matched-budget ignition harness
make recursive research executable without giving candidates control of their
evaluator. The checked-in [`autoresearch evidence`](docs/VNEXT_AUTORESEARCH_EVIDENCE.json)
contains zero genuine private trials and supports no self-improvement or
ignition claim; source edits, runtime application, automatic promotion,
execution, and capital authority remain absent.

The [`final master-plan audit`](docs/VNEXT_MASTER_PLAN_FINAL_AUDIT.md) maps all
38 design sections to concrete evidence and verifies the complete 20-step
forecast capability. Its result is `PASS_WITH_EMPIRICAL_GATES_OPEN`: the
architecture is integrated, but material improvement remains unestablished and
vNext remains `SHADOW_ONLY`. Historical dashboards are route-lazy-loaded, which
preserves all 293 archived views while reducing the production entry bundle
from 720.51 KB to 302.00 KB.

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

The latest checked-in [`evidence and performance cycle`](docs/EVIDENCE_PERFORMANCE_CYCLE_2026-07-15.json)
grades 4,772 decision snapshots across 1,312 event clusters. Aggregate Brier
skill remains positive (+5.40%), but verified fill P&L is -251c and crypto
fill-conditioned skill is -21.41%, so canary and scale remain blocked. Current
sports settlement evidence is MLB-only: exact joint-cohort guards quarantine
pregame underdog totals and balanced-price winners while continuing shadow
grading; no conclusion is transferred to another league.

The local command-center dashboard at `http://127.0.0.1:8787/` (durable via the
`DummyDashboard` scheduled task; run `scripts/install_dashboard_task.ps1`, which
self-elevates through a UAC prompt) tracks scheduler
health, active and settled paper trades, decision explanations, lane-level
calibration and P&L, target-evidence progress, weaknesses, and promotion gates.
It also exposes the isolated forced-coverage ledgers for every designated
crypto scope and sports prediction type so missing markets, explanations, and
settlements are visible without contaminating promotion evidence, plus a
council-of-specialists panel (status, season state, settled/contested
evidence volume, CLV, open opportunities per specialist — read-only, fails
closed to an empty panel when no snapshot has been written yet). Its Start
and Stop controls only enable or pause the paper schedulers; they cannot reach
live execution, credentials, risk settings, or capital.

![Dummy paper trading command center](docs/assets/dummy-paper-dashboard.jpg)

## Council of specialists

Every vertical (MLB, NBA, NFL, NCAAF, NHL, NCAAMB, crypto) is owned end-to-end
by its own specialist subagent behind one protocol — pre-game forecast,
in-play view, independent sharp "book" estimator, feed warmup, and health
(`autonomy/specialists/`). Routing is disjoint (one market, one specialist)
and every specialist fails closed: missing data means abstain, never a
degraded guess. NBA/NHL plus separate NFL, NCAAF, and NCAAMB live-state
models expose in-play winner/spread/total views; de-vigged ESPN event-summary
moneylines and exact-strike spread/total lines supply the independent live
book legs. ESPN exposes one current main spread/total, so unmatched alternate
strikes use an explicit league-width challenger curve anchored to that
de-vigged main price; malformed or one-sided books still abstain. Verified hard
ESPN availability statuses apply bounded position-weighted pregame margin
adjustments, while soft statuses widen uncertainty only; explicit play-by-play
ejections are receipt-timestamped, evidence-only
opportunist context and never double-adjust the live score. MLB can replace its
incumbent live opinion with a distinct StatsAPI plate-appearance challenger only
when both starters, confirmed 9-player lineups, and at least 75% batter-rate
coverage are present; hydration failure preserves the incumbent path. Leagues
auto-wake/sleep with their real season (ESPN
scoreboard window, no hardcoded calendar), CLV-vs-closing-line and
settlement-backed contested Brier both accrue per specialist as challenger
evidence, and a human-gated propose-then-promote pipeline is the only way
evidence ever reaches the execution ensemble. The dashboard's council panel
(below) surfaces per-specialist status, season state, evidence volume, and
CLV read-only. Details: [docs/AUTONOMY.md](docs/AUTONOMY.md#council-of-specialists).

The market-state routing that assigns one specialist per market — the layer
that decides *"who governs this market"* — is documented in
[docs/MARKET_STATE_ROUTING.md](docs/MARKET_STATE_ROUTING.md).

**Power-ratings ensemble.** Each team league carries a challenger that blends
several independent rating sources — ESPN FPI/BPI (keyless, first-party),
in-house Elo, and in-house Massey (ridge least-squares over margins) and Colley
(win-loss matrix) ratings computed from public settled scores — into one
consensus point margin. Each source declares its own point-margin scale, and
the ensemble prices a coherent winner-plus-spread ladder from a single
distribution plus an opportunistic divergence flag when the ensemble and the
league kernel disagree while sources agree. It is challenger-only: it accrues
CLV and Brier evidence but never reaches capital until an explicit human
promotion. No ratings site is scraped; the Massey and Colley methods are
replicated in-house from public final scores. Completed ties remain explicit
feed facts and enter Colley as half a win plus half a loss for each team;
unresolved results remain excluded. NCAAF uses its own compound-Poisson
scoring-event distribution for both its specialist and power-ratings paths,
not the NFL absolute-margin tilt.

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
  globally, per-vertical (`source@VERTICAL`), and at the exact
  source × market-type × phase/horizon scope — and updates trust
  multiplicatively. Influence is earned by beating the market, nothing else.
- **Autonomous recursive repair**: every metabolic recalibration diagnoses
  fill and sports performance by independent event clusters, relearns exact-
  scope trust, and writes contraction-only joint cohort quarantines. A guarded
  cohort abstains but keeps producing shadow grading evidence, so recovery can
  be measured and proposed for human release later. Quarantines are sticky;
  positive results can request human review, but cannot auto-promote, restore
  an execution path, enable execution, or increase capital.
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
- **Crypto correlation control**: Coinbase flat-vol, blend-sigma, and empirical
  regime transforms share one distribution family; macro-regime and
  crypto-equity drift share one cross-asset family. Enabling correlated
  challengers can redistribute family weight but cannot manufacture additional
  precision. Crypto retains a 25% market anchor and challengers remain excluded
  until explicit promotion review.
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
  sessions but has no credentials, broker, readiness, execution, or capital
  authority. A physically separate coverage-probe ledger also forces a paper
  side for every real, valid nearest-expiry crypto target in all 12 asset/horizon
  scopes, records the normal-policy blocker, and exposes missing scopes as gaps.
  Forced crypto samples cannot influence calibration, promotion, readiness, or
  execution.
- **Multi-sport game engine**: MLB, NFL, NCAAF, NHL, NBA, and NCAAB
  challengers feed a deterministic replay buffer and Monte Carlo curriculum.
  League-isolated genomes progress through Rookie/Veteran/Elite/Boss tiers,
  face fog-of-war/meta-shift/boss-chaos arenas, and unlock mutation skills only
  after settled event-cluster evidence. Deep analytics include Brier, log loss,
  ECE/MCE, AUC, sharpness, Sortino, drawdown, and paired-cluster confidence.
  A separate forced-coverage lane paper-trades every real, signal-compatible
  designated winner/total/YRFI-NRFI market and explains the decision;
  missing types become explicit coverage gaps. Forced samples cannot promote a
  model, rewrite code, alter production weights, or reach capital. NFL winner
  is also retained as an explicit gap while listed contracts accumulate
  scope-specific forward settlement and calibration evidence.
- **Loss-deconstruction evolution engine**: a deterministic nightly pass groups
  settled trades by grading scope, finds where the system bleeds versus the
  market (cluster-level Brier shortfall with 95% intervals and disclosed family
  size), and buckets each bleeding scope by feature regime, market type, and
  phase. An LLM narration layer adds plain-language commentary per scope. The
  output is a read-only artifact that orders the tuner's target priority
  (non-gating) and surfaces a "where we bleed" line on the dashboard — it
  mutates no source, parameter, or promotion.
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
- **Repository quality gate**: `python -m ruff check .` must pass
  repository-wide. Exceptions are restricted to immutable vendored snapshots,
  archived historical layouts, and executable path-bootstrap scripts; active
  forecasting, safety, and test code remains fully checked.

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
python scripts/run_dummy_ledger_retention.py                 # dry-run: settled signals older than 7d
python scripts/run_dummy_ledger_retention.py --apply --vacuum # verified archive, then reclaim hot DB pages
```

Ledger retention moves only immutable signal rows for markets settled longer
than seven days into `runtime/autonomy/archive/signals_archive.db`. Every batch
must match exact row counts and a SHA-256 content digest before the hot rows are
deleted in the same SQLite transaction. Research readers use the unioned
`signal_history` view, so calibration/readiness evidence remains unchanged;
decisions, outcomes, settlements, trust, promotions, and execution files are
never eligible. Dry-run is the default. Stop ledger-writing tasks before an
`--apply --vacuum` maintenance pass.

The hourly trainer also runs the quarantined recursive evolution lab. It
mutates bounded research genomes, replays them causally, stress-tests degraded
execution, and accumulates later forward evidence without changing production
code, weights, risk, orders, or capital. See `docs/EVOLUTION_LAB.md`.

Details: [docs/AUTONOMY.md](docs/AUTONOMY.md).
Training protocol: [docs/SIMULATION_TRAINING_REGIMEN.md](docs/SIMULATION_TRAINING_REGIMEN.md).
Crypto audit: [docs/CRYPTO_PERFORMANCE_AUDIT.md](docs/CRYPTO_PERFORMANCE_AUDIT.md).
Evidence governance review: [docs/EVIDENCE_GOVERNANCE_REVIEW_2026-07-14.md](docs/EVIDENCE_GOVERNANCE_REVIEW_2026-07-14.md).
Crypto paper twin: [docs/CRYPTO_PAPER_TWIN.md](docs/CRYPTO_PAPER_TWIN.md).
vNext integration plan: [docs/VNEXT_MASTER_PLAN_INTEGRATION.md](docs/VNEXT_MASTER_PLAN_INTEGRATION.md).
