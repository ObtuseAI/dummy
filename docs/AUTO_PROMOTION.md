# Autonomous Thresholded Promotion

**Owner directive: 2026-07-16.** Promotion gates become autonomous — a scope
with statistical proof of profit auto-promotes into the fused ensemble. This
replaces the previous human-only positive promotion (WS-14's
`promotion_activation: HUMAN_ONLY`).

**What is explicitly NOT changed:** live trading authorization.
`configs/live_submit.json`, the second-proof sequence, and session live auth
remain **operator-only**. The autonomous ladder governs **fusion membership
only** — which challenger scopes the `EnsembleForecaster` blends, and at what
weight. Nothing in this system can place, size, or authorize a live order.

## Components

| Piece | File |
| --- | --- |
| Decision engine (pure) | `autonomy/auto_promotion.py` |
| I/O runner (gather → decide → apply) | `autonomy/auto_promotion_runner.py` |
| Hash-chained audit ledger | `autonomy/promotion_ledger.py` → `runtime/autonomy/promotion_ledger.jsonl` |
| Stage-aware registry | `autonomy/promotion.py` (`PromotionRegistry.stage_for` / `weight_multiplier`) |
| Fusion enforcement | `autonomy/forecaster.py` (`fuse` filter + probation weight cap) |
| Daily schedule | inside the existing `DummyReadinessReport` task via `scripts/run_dummy_readiness_report.py` (no new schtasks; re-running the install script is optional — the task definition is unchanged) |
| Dashboard surface | `auto_promotion` key in `assemble_dashboard_state` (reads `runtime/autonomy/auto_promotion_state.json`) |

Scopes are the exact four-axis cohorts from WS-15:
`source | subject | market_type | horizon_or_phase`. Evidence never pools
across subjects, market types, or horizons.

## The ladder

### Stage 1 — probation (capped fusion weight)

A never-promoted, challenger-gated, emission-stamped `promotion_eligible`
scope promotes when **ALL** of the following hold:

| # | Criterion | Threshold | Measured from |
| --- | --- | --- | --- |
| (a) | Contested event-clusters | ≥ **300** (≥ **450** if no CLV instrumentation) | settled, market-benchmarked emissions (`load_settled_rows`), contested = ≥ 5c disagreement with the market prior |
| (a) | Evidence span | ≥ **7 calendar days** | first→last contested emission timestamp |
| (b) | Cluster-robust contested Brier edge vs market, CI95 lower bound | > **0** | event-cluster bootstrap (1000 resamples, deterministic per-scope seed); Bonferroni-widened by mined-family size where applicable |
| (b) | Contested beat rate | ≥ **0.55** | share of contested emissions whose Brier beats the market's |
| (c) | **Proof of profit**: fee-adjusted counterfactual P&L, cluster-level bootstrap CI95 lower bound | > **0** | entry at the recorded market price at emission time, exit at settlement, Kalshi **maker** fee model (`autonomy/fees.py`; Dummy rests limit orders). Cluster-level, never per-emission |
| (d) | Not degrading | trailing-100-cluster mean edge ≥ −0.005 | existing degradation check (`autonomy/promotion.py`) |
| (e) | CLV mean CI lower bound | > **0** where CLV records exist for the scope's `specialist\|market_type` grain | `runtime/autonomy/clv_report.json`. Scopes with no CLV instrumentation (sports today) may pass without it but require the 450-cluster bar in (a) |
| (f) | Correlation guard | max emission correlation vs every already-fused source on ≥ 5 overlapping markets ≤ **0.8** | Pearson over ticker-mean probabilities. If exceeded, the scope is **not added** — it is flagged as a *replacement candidate* only (reported; no action) |

A stage-1 scope fuses at **25% of its earned trust weight**
(`STAGE1_WEIGHT_FRACTION`, configurable via `PromotionConfig`). The cap is
applied inside `EnsembleForecaster.fuse` via
`PromotionRegistry.weight_multiplier_for_signal`, so champions and legacy
full-weight human promotions are byte-identical to before.

### Stage 2 — full weight

A stage-1 scope escalates to full weight when it has accrued:

* ≥ **50** settled scope-attributed paper/shadow trades (share-weighted
  attribution from `sources_used` on verified settled fills), and
* realized P&L cluster-level bootstrap CI95 lower bound > **0**.

### Demotion — instant, both stages, looser thresholds (hysteresis)

The existing automatic demotion stays and applies at both stages: a promoted
scope demotes **immediately** when its trailing-200-cluster contested-edge
CI95 **upper** bound < 0. Promotion needs the CI95 **lower** bound > 0, so
there is a wide no-churn band between "confidently good" (promote) and
"confidently bad" (demote): a boundary scope neither promotes nor demotes
repeatedly. Demotions are sticky (`auto_demotions.json` never un-sticks
without a human) and are never counted against the daily cap — de-risking is
uncapped.

## Rails (all mandatory, fail-closed)

The daily promotion run **aborts entirely** — promoting nobody — when any of
these trips. Aborts are themselves chained + alerted (`PROMOTION_RUN_ABORTED`)
so a silent stand-down is impossible.

1. **Daily cap:** max **2** autonomous add-risk actions (promotions +
   escalations combined) per UTC calendar day, counted from the hash chain.
   Excess candidates are deferred (strongest evidence first; deterministic
   tie-break by scope name).
2. **Kill file** present (`runtime/autonomy/KILL`).
3. **Heartbeat** shows `CYCLE_ERROR*`, or is not alive.
4. **Health errors:** any signal source currently quarantined by the circuit
   breaker (`source_health.json`).
5. **Weight-saturation anomaly:** any trust weight pinned at the learner's
   multiplicative ceiling (8.0).
6. **Exchange anomaly:** venue reports inactive/trading-halted, or its status
   cannot be fetched (unknown defers promotion; there is no urgency to add
   risk).
7. **Evidence artifacts stale (> 24 h):** the heartbeat's last cycle (the
   evidence pulse) or a present-but-old CLV report.
8. **Broken hash chain:** if `promotion_ledger.jsonl` fails verification, no
   new promotion can be authorized and the daily cap cannot be counted —
   abort.

## Audit trail

Every promotion / escalation / demotion / abort appends one record to
`runtime/autonomy/promotion_ledger.jsonl` — an append-only, hash-chained log
(sha256 over the canonical body, each entry linking to the previous entry's
hash; same pattern as `dummy/intelligence_lab/scientific_memory.py`). The
payload embeds the **full evidence dossier**: every threshold value beside the
measured value, per criterion, plus the active `PromotionConfig`. The same
event emits an operator alert (`AUTO_PROMOTION` / `AUTO_ESCALATION` /
`AUTO_DEMOTION`, `autonomy/alerts.py`) and lands in the dashboard state JSON
under `auto_promotion`.

`promotions.json` is now written by the engine (schema version 2: entries gain
`stage`, `weight_fraction`, `promoted_by`, `evidence_ref` = the chain hash).
Reads are backward-compatible: empty/missing files promote nobody; legacy
human entries without the new keys are treated as stage-2 full-weight.

## Multiple-testing honesty (mined families)

A scope originating from a strategy-miner family (`autonomy/strategy_miner.py`
disclosed `rules_tested` for its proposal) must carry that family size in
`runtime/autonomy/mined_scope_families.json` (`{scope: family_size}`, written
at rule-adoption time). The engine widens the Brier-edge bootstrap CI by a
Bonferroni correction (tail quantiles at `0.025 / family_size`) before the
criterion-(b) comparison, so a lucky member of a large searched family cannot
promote on noise. Unlisted scopes use family size 1.

## Determinism

Same inputs → same decisions. All bootstraps are seeded per scope; the engine
consults no wall clock (the runner injects `now_ts` / `now_iso`); candidate
ranking ties break lexicographically. Every rail and every criterion has a
dedicated unit test (`tests/test_auto_promotion.py`,
`tests/test_auto_promotion_runner.py`, `tests/test_promotion_ledger.py`).

## Why these thresholds

* **300 clusters / 7 days:** ~the point where a cluster-bootstrap CI on Brier
  edge stabilizes for our densest scopes (crypto 15m accrues ~20–40
  clusters/day); the span floor blocks a one-hot-week promotion.
* **CI lower bound > 0, cluster-level:** per-emission CIs are dishonest under
  correlated same-event emissions — the repo-wide cluster rule
  (strategy miner, CLV, backtest) applies unchanged.
* **Beat rate 0.55:** matches the canary gate's `MIN_CONTESTED_BEAT_RATE`; a
  positive mean edge with a sub-coin-flip beat rate is a few-lucky-hits
  profile.
* **Fee-adjusted counterfactual P&L:** Brier edge is a proper-score edge, not
  money. A scope can beat the market statistically and still lose after fees
  at the prices it actually contests; proof of profit closes that gap using
  the maker fee model the executor actually trades under.
* **Probation at 25%:** a newly promoted scope influences the ensemble enough
  to accrue realized attribution (stage-2 fuel) but cannot dominate fusion
  before real money-shaped evidence exists.
* **2/day cap:** bounds the blast radius of any systematic evidence defect to
  two capped-weight scopes per day, with demotion always instant.
