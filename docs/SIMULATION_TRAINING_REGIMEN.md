# Dummy simulation-training regimen

This is a report-only accelerator that runs beside the ten-minute shadow
collector. It is designed to find better policies sooner without confusing
synthetic performance with verified prediction-market success.

## Safety and evidence boundary

- The trainer opens `runtime/autonomy/ledger.db` with SQLite `mode=ro` and
  `PRAGMA query_only=ON`.
- It has no executor, broker, credential, network, weight-update, risk-cap, or
  readiness-write path.
- Every report declares `execution_authority=false`, `weights_written=false`,
  `risk_caps_written=false`, and `readiness_evidence_written=false`.
- Simulated results never count toward canary or scale. A proposal must first
  survive a later unseen shadow experiment and then earn verified settled-fill
  P&L.

## Curriculum

### 1. Forecast-selectivity training

The trainer searches 60 shrinkage, edge-threshold, and uncertainty policies.
It uses nested expanding windows:

1. train only on outcomes whose `settled_at` precedes the next test window;
2. purge test rows from event clusters already present in training;
3. rank candidates on lower-bound mean P&L after taker fees and 1-cent
   slippage, then drawdown and simplicity;
4. compare the selected challenger against the incumbent on the untouched
   next fold.

A forecast challenger is only eligible for a new shadow experiment after at
least three later folds, two positive folds, positive lower-95% mean P&L,
higher aggregate P&L than the incumbent, and no worse maximum drawdown.
Eligibility does not apply the policy.

### 2. Execution-selectivity training

The trainer searches recorded combinations of maximum uncertainty, minimum
EV, maximum queue ahead, and maximum entry price. It uses witnessed shadow
order truth only. No submitted order is called a fill.

An execution challenger remains `HOLD` until its filtered sample contains at
least 30 known order outcomes, 20 settled fills, positive net P&L, and a
positive lower-95% mean P&L. It is then eligible only for a bounded shadow
experiment.

### 3. Compounding stress

Out-of-sample challenger trades are resampled by correlated event cluster,
not as independent contracts. Candidate bankroll fractions of 0.25%, 0.5%,
1%, and 2% are tested with 0, 2, and 5 cents of additional slippage.

The highest stress-safe fraction must retain starting bankroll at the fifth
percentile, keep 95th-percentile drawdown within 10%, and keep loss probability
at or below 25% under the 5-cent scenario. It must also participate in at least
half of out-of-sample opportunities (and at least ten); a tiny fraction cannot
look safe merely because it cannot afford the losing cases. This is a
shadow-sizing proposal, never live authority. Real risk remains downstream of
the existing risk brain, drawdown ladder, canary gate, and per-order firewall.

### 4. Recursive evolution lab

The trainer maintains a quarantined research genome across hourly runs. New
settlements advance its generation; unchanged evidence does not. Each
generation creates bounded local mutations plus broad challengers, selects
them inside settlement-lagged folds, purges repeated event clusters, and tests
the winners under wide-spread, edge-decay, and severe-liquidity stress.

One active research epoch accumulates only decisions created after the epoch
started. It cannot be reset merely because another hourly run occurs. A
report-only candidate may rotate after at least 30 forward trades across five
clusters if it fails and a new retrospective challenger passes. Explicit
shadow review still requires 100 forward trades across ten clusters, positive
lower-95% mean P&L, and positive paired cluster-bootstrap advantage.

The evolution lab may mutate and rotate JSON research descriptions only. It
has no production-code, deployment, weight, risk, order, or capital authority.
See `docs/EVOLUTION_LAB.md`.

## Operating cadence

- Every 10 minutes: existing public shadow collection and reconciliation.
- Every 60 minutes: simulation curriculum against the enlarged ledger.
- Every settlement: existing source calibration and trust learning.
- Every ~6 hours: existing metabolic full backtest/bootstrap.
- Daily operator/readiness review: compare simulation proposals with newly
  verified fills; do not promote on forecast-surface results alone.
- At each 20-settled-fill boundary: rerun the full autonomy/firewall suite and
  review canary and scale gates separately.

The hourly job is deliberately offset from the shadow collector and uses an
atomic lock plus atomic report writes.

## Commands

```powershell
python scripts/run_dummy_simulation_training.py --summary
powershell -ExecutionPolicy Bypass -File scripts/install_simulation_training_task.ps1
Get-ScheduledTask -TaskName DummySimulationTrainer
```

Reports are written to `artifacts/dummy/simulation_training/`; `LATEST.json`
is an atomic pointer to the most recent run.

The hourly report also embeds `crypto_execution_truth`: filled crypto Brier
versus market, source-family overlap, anchor-blend replay, and the observed
EV/price/no-pyramiding guard counterfactual.

It additionally embeds `execution_trace_replay` and `evolution_lab`. The
runtime dashboard shows the active genome, generation, new settled evidence,
forward trade/cluster count, forward P&L, and the unchanged authority boundary.

## What accelerates readiness

The curriculum accelerates parameter rejection and shadow-experiment design.
It cannot accelerate the calendar time required for orders to fill and settle.
Readiness still requires positive verified P&L and positive fill-conditioned
forecast skill; that separation is intentional.
