# Execution-policy tournament (Wave-2 WS-A2/F2)

Implements the Phase-A execution-policy tournament recommended by the
adverse-selection diagnosis (`docs/EXECUTION_ADVERSE_SELECTION_2026-07-16.md`).
That diagnosis established that Dummy's maker-first execution channel converts a
modestly positive-skill forecast surface into a losing book: maker fills run
**−14.7%** Brier vs market while the unfilled surface runs **+6.5%**, fast
(≤60s) fills are 11% win / −300¢, every fill carries **+13.3¢** of pure adverse
information, and the taker counterfactual over the full actionable surface is
near breakeven.

The tournament tests **execution policy**, not forecast policy, with the
incumbent maker as the control.

## What ships

- **`autonomy/execution_policy.py`** — a typed, frozen `ExecutionPolicy`
  (maker / taker / hybrid + guard parameters) and the five canonical cohorts.
  Consumed by `autonomy.executor.Executor` (see below) and by the tournament.
- **`autonomy/execution_tournament.py`** — replays the ledger's actionable
  decision surface under each cohort and reports, per cohort, cluster-robust
  realized/counterfactual P&L, fill-conditioned Brier edge vs market, fill rate,
  and per-fill slippage, each measured against C0. Includes the C2 walk-forward
  threshold selection.
- Wiring: `autonomy.backtest.run_backtest` carries `execution_tournament`;
  `summarize_backtest` carries the compact view;
  `scripts/run_dummy_backtest.py` emits
  `runtime/autonomy/execution_tournament.json`; the dashboard `/api/status`
  payload exposes the compact panel; `autonomy.alerts` gains
  `EXECUTION_TOURNAMENT_GATE`.

## Cohorts

| Cohort | Policy | Replay semantics over the actionable surface |
|---|---|---|
| **C0** | maker-only control (incumbent) | the witnessed maker fills exactly as realized (per-contract maker sim at the recorded fill price + maker fee) |
| **C1** | taker-only | cross the market midpoint at decision time over the **whole** surface, taker fee, keep rows whose chosen-side EV net of the taker fee clears MIN_EV |
| **C2** | taker + walk-forward edge threshold | C1 plus a minimum \|model−market\| edge chosen **per fold** by the walk-forward selector; only out-of-sample fills count; per-fold picks are disclosed |
| **C3** | adverse-guard maker | witnessed maker fills censored by the fast-cross guard (drop fills ≤60s) and the divergence cap (drop \|model−market\| > 10¢); presubmit book recheck |
| **C4** | hybrid patient-then-take | maker fills inside the 60s rest window stay maker; every other actionable row crosses as a taker at the deadline subject to the EV floor (so C4 also captures the winners the maker never fills). For 60s-TTL crypto, C4 ≈ C1 |

Every interval is **cluster-level** (per event-cluster mean, bootstrap over
clusters) — never a per-emission CI. The success gate is **≥ 40 witnessed (or
would-have-witnessed) fill event clusters per cohort**; below the floor a cohort
is `insufficient_clusters` and its point estimates are directional only.

## C0 reproduces current behavior exactly

`Executor` accepts an optional `execution_policy` (default:
`ExecutionPolicy.maker_only_control()`). When the policy **is the control**,
`execute()` takes the exact pre-existing code path with zero new branches — C0
is byte-identical to today (regression-tested in `tests/test_execution_policy.py`:
default vs explicit control produce identical `TradeOutcome`s). Only a
non-control policy consults the guard hooks; the adverse-guard maker (C3) can
refuse a quote whose model diverges from the supplied market prior beyond the
cap (fail-open when no prior is available). The live executor stays maker-first
and never crosses the spread here; the taker/hybrid P&L is measured
**counterfactually** in the replay layer.

## Why this home, and no new schtask

The tournament is an **evaluation layer** on the existing backtest pipeline
(`scripts/run_dummy_backtest.py` → `run_backtest`), which the live machine
already schedules to produce `latest_backtest_summary.json`. Per-cohort
fill-conditioned evidence therefore accrues automatically every backtest cycle
with no new scheduled task. It reuses the adverse-selection module's
actionable-surface reconstruction and cluster bootstrap so the two artifacts are
directly comparable. (The `crypto_paper_twin` lane was considered; its 1h lanes
are quarantined on the base branch and it books a separate simulated-taker book
rather than the live maker-fill surface the diagnosis measures, so the backtest
pipeline is the cleaner home for a policy tournament grounded in real fills.)

## Winner determination is evidence-only

**The report ranks cohorts; it does NOT switch the live execution policy.**
Adopting a cohort as the live policy flows through one of two existing paths,
never automatically from this report:

1. **The auto-promotion ladder** (`autonomy/auto_promotion.py` /
   `autonomy/promotion_ledger.py`) — the same fusion-membership governance that
   already gates behavior changes on cluster-robust contested evidence and a
   human-reviewed rung. This is the intended path once a challenger cohort
   clears the ≥40-cluster gate and its cluster-robust P&L / Brier-edge CI vs C0
   is decisively positive.
2. **An explicit, reviewed operator config change** — for an out-of-band switch.

Rationale: the maker-fill sample is small (the diagnosis had 27 settled fills /
22 clusters), the cluster CIs straddle zero, and the taker cohorts are
*counterfactual* (they never assume a resting maker quote would have filled).
An automatic switch off a directional point estimate would repeat exactly the
selection error the diagnosis identified. The report exposes
`policy_switch_authority.auto_switch = false` and emits an informational
`EXECUTION_TOURNAMENT_GATE` alert when a challenger first clears the gate, as a
review prompt — not an action.
