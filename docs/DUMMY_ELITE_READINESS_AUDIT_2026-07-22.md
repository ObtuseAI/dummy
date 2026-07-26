# Dummy elite-readiness audit

**Audit date:** July 22, 2026  
**Repository:** `C:\src\engine\dummy`  
**Verdict:** Dummy is a strong, substantially hardened research, shadow-trading, and operator-observability platform. Its exact four-model OpenRouter panel is live-proven. **Real-money profitability is not proven, and Dummy is not ready to deploy capital.** The fresh evidence is negative or incomplete, so live model calls and live order submission should remain locked.

This is an evidence verdict, not a promise of profit. No audit, model panel, backtest, or UI can guarantee wealth or extraordinary prediction accuracy.

## Executive scorecard

| Area | Status | Evidence-backed conclusion |
|---|---|---|
| Engineering platform | **Strong** | Centralized execution, fail-closed authority, bounded evidence jobs, provider-network controls, broad automated coverage, and production UI are in place. |
| OpenRouter connectivity | **Live proven** | All four exact model identities returned HTTP 200 with valid task-shaped schemas in one attempt each. |
| Sports and crypto research | **Operational** | Daily sports guide and bounded crypto horizon collection work, but strict sports holdout evidence and mature cross-horizon crypto evidence are not yet sufficient. |
| Demonstrated edge | **Narrow and unpromoted** | Three scopes pass the current no-edge map; 62 show no demonstrated edge, seven are significantly negative, and 107 are insufficient. |
| Fresh realized performance | **Negative** | The fresh receipt-bounded backtest's 37-trade realized-decision slice lost 669 cents with -26.09% ROI. |
| Promotion readiness | **Blocked** | 273 scopes evaluated; zero promotion candidates. |
| Live capital readiness | **Not ready** | Live submission is off, model paid-call gate is locked, execution authority is false, and this audit made zero live-order submissions. |

## OpenRouter four-model arsenal

The existing `OPENROUTER_API_KEY` was found in the project environment without exposing it. The authenticated four-call smoke stored no prompt response content or secret. The exact requested and returned identities matched:

| Model | Routed role | HTTP / schema / identity | Reported cost |
|---|---|---|---:|
| `google/gemini-3.6-flash` | Rapid evidence extraction and independent forecast | 200 / valid / exact | $0.000414 |
| `openai/gpt-5.6-luna` | Low-latency structured forecast and research-only trade draft | 200 / valid / exact | $0.000316 |
| `anthropic/claude-sonnet-5` | Market thesis, strategy critique, synthesis, and reflection | 200 / valid / exact | $0.000608 |
| `z-ai/glm-5.2` | Independent risk, calibration, no-trade, and hypothesis critique | 200 / valid / exact | $0.000935484 |

**Result:** 4/4 `LIVE_PROVEN`; total reported successful-run cost **$0.002273484**. See the redacted [live smoke artifact](C:/src/engine/dummy/artifacts/dummy/openrouter_four_model_smoke_v1.json), [routing configuration](C:/src/engine/dummy/configs/model_routing.json), and [provider-panel evidence note](C:/src/engine/dummy/docs/OPENROUTER_FOUR_MODEL_PANEL_2026-07-22.md).

The production state remains intentionally fail-closed:

- configuration gate: **OFF**;
- dashboard-process runtime opt-in: **ON**;
- effective two-key paid-call gate: **LOCKED**;
- model evidence, probability, and order authorities: **false**;
- live submit: **off** in [live_submit.json](C:/src/engine/dummy/configs/live_submit.json);
- live-order submissions made by this audit: **zero**.

The dashboard reads the stored redacted smoke artifact and local configuration only; it cannot initiate a provider call or mutate authority.

## What was hardened

### Provider and model authority

- Real provider transport now requires a strict literal opt-in plus an opaque, process-local capability. HTTPS host approval and credential-to-host binding are enforced before key access or network I/O. The legacy resolver is preflight-only by default and its alias probes are bounded.
- Pytest interlocks the production asynchronous HTTP provider transport against approved real model hosts while preserving `httpx.MockTransport` tests. This is transport-specific defense in depth, not an operating-system network sandbox.
- The atomic panel fails closed on an invalid member. An authorized, contract-valid panel's no-trade output is a hard veto before proposal, risk, and firewall stages.
- Model influence is limited to exact scopes: crypto `15m`, `1h`, `1d`, and `1w`; sports `pre` and `live`. Sports phase is tri-state: missing, malformed, unrecognized, conflicting, or merely `active` phase evidence becomes `unknown`, which is non-promotable and blocked before order submission rather than inheriting pregame authority.
- Every production order request must carry a typed, SHA-256-bound model-influence attestation covering the forecast, edge, confidence, provenance, proof, proposal, risk, and expiry. The attestation has a derived 30-second lifetime, allows at most five seconds of future clock skew, cannot revive a stale forecast, and is bounded by forecast and order expiry. Missing, tampered, stale, or out-of-scope attestations are rejected by the firewall.

Key implementation evidence: [network capability](C:/src/engine/dummy/model_router/network_capability.py), [provider sink](C:/src/engine/dummy/model_router/providers.py), [model authority](C:/src/engine/dummy/forecasting/model_probability_authority.py), [influence attestation](C:/src/engine/dummy/forecasting/model_influence_attestation.py), and [live firewall](C:/src/engine/dummy/live_firewall/firewall.py).

### Execution truth and risk

- Exactly one production order-creation caller remains: the central firewall. Retired alternate adapters cannot create orders.
- The broker path re-fetches book depth, market status, expiry, and identity; sizes against the full taker quantity and side-specific depth; and persists reservations before submission.
- Positions and P&L derive from reconciled fills, not submissions or requested quantities. Partial fills, fees, shadow books, and live books remain distinct.
- Live submit, caps authority registration, allowed-market authority, and kill-switch requirements remain fail-closed. No safety gate was weakened to improve a report.

### Prediction scope and bounded research

- Weather and commodities are data/context inputs only. They are blocked from prediction targets, betting-guide candidates, strategies, and execution.
- Crypto research explicitly covers `15m`, `1h`, `1d`, and `1w` horizons. Persistent cursors, fair series rotation, market caps, settlement caps, and cooperative deadlines prevent evidence scans from monopolizing the daemon.
- Backtest evidence uses receipt-bounded live source snapshots and set-based, point-in-time queries instead of repeated full-ledger/N+1 scans.
- Sports temporal evaluation excludes rows with unknown availability rather than silently treating retrospective data as point-in-time evidence.

## Current economic evidence

### Fresh point-in-time backtest

The fresh [backtest summary](C:/src/engine/dummy/runtime/autonomy/latest_backtest_summary.json) and [full artifact](C:/src/engine/dummy/artifacts/dummy/backtests/AUTONOMY_BACKTEST_20260722T105354225207.json) were generated from **284,325 settled markets** under source mode `live_only_receipt_bounded_v1`.

The realized-decision slice is not profitable:

- trades: **37**;
- net P&L: **-669 cents**;
- ROI on 2,564 cents entry cost: **-26.09%**;
- win rate: **32.4%**;
- profit factor: **0.5703**;
- maximum drawdown: **796 cents**;
- mean trade P&L 95% interval: **[-44.83, 8.67] cents**;
- production weights written: **false**.

The broader expanding-window out-of-sample policy was also negative: 6,536 trades, -3,761 cents, -0.95% ROI, and 0.9653 profit factor. Forecast Brier was 0.143426 versus the market's 0.141139, with -0.0162 Brier skill and detected negative drift. These results directly reject a live-profitability claim today.

### Negative controls and no-edge map

The [negative-control report](C:/src/engine/dummy/runtime/autonomy/negative_control_report.json) is `CLEAN`: 48 sources screened, 37 powered, 11 insufficient, and zero flagged. `CLEAN` means the configured leakage/randomness screens passed; it does **not** mean a strategy is profitable.

The [no-edge map](C:/src/engine/dummy/runtime/autonomy/no_edge_map.json) contains:

- **3** edge scopes;
- **62** scopes with no demonstrated edge;
- **7** significantly negative scopes;
- **107** insufficient-evidence scopes.

The three narrow historical edge candidates are:

| Scope | Event clusters | Mean Brier advantage | 95% interval |
|---|---:|---:|---:|
| `crypto_equities_flow|sol|15m_direction|15m` | 172 | 0.020808 | [0.004111, 0.038782] |
| `crypto_macro_regime|sol|15m_direction|15m` | 188 | 0.017081 | [0.000399, 0.034623] |
| `market_debias|mlb|na|pre` | 96 | 0.088822 | [0.060314, 0.115540] |

They are research candidates, not permission to trade. The seven significantly negative scopes include BTC hourly ladder signals and the BTC 15-minute technical-foundry scope; they should remain quarantined.

### Readiness and sports holdout

The [readiness report](C:/src/engine/dummy/runtime/autonomy/readiness_report.json) evaluated **273 scopes** and produced **zero promotion candidates**. Its `autonomous_gate_evaluation=true` means the gate ran, not that the gate passed. The displayed 96.97% fused-pick hit rate is dominated by an `other|other` cohort of 111,704 rows, 110,205 of which fall in the extreme probability bins, and is not betting-profitability proof.

The strict [2025 MLB temporal holdout](C:/src/engine/dummy/runtime/autonomy/sports_temporal_holdout_mlb_2025.json) is `BLOCKED_INSUFFICIENT_POINT_IN_TIME_SEASONS`: all 5,495 candidates had unknown availability timestamps, so zero were eligible and the sealed holdout was not consumed. Execution, promotion, and capital authority all remain false.

### Crypto multi-horizon evidence

Four bounded rotation cycles across 13 configured series processed **725 markets**, wrote **14,500 forecast attempts**, and recorded **576 new settlements**. Cumulative settled evidence reached **8,311 forecasts**. The latest bounded sweep has a persistent 517-ticker reconciliation backlog.

The collection covers `15m`, `1h`, `1d`, and `1w`, but the cycles are intentionally partial and the evidence is not yet mature enough to establish robust independent edge at every horizon. Every artifact is research-only with execution, capital, promotion, production-weight, risk, and gate-write authority set to false. See [latest crypto horizon evidence](C:/src/engine/dummy/artifacts/dummy/crypto_horizon_evidence/LATEST.json).

## Desktop UI/UX verification

The actual Totalizator desktop web surface at `http://127.0.0.1:8787` was exercised in a real browser, not just unit-tested.

- Model Arsenal shows the exact four models, redacted key source, 4/4 stored live proof, total cost, configuration/runtime/effective gates, and false authority.
- The July 22 sports-guide snapshot showed **16 MLB events / 1,528 priced markets** and **6 WNBA events / 129 priced markets**. These are daily inventory counts, not profitable-bet claims.
- Non-All market tabs actually filtered rankings and counts. MLB prop rows identified players by name; WNBA Moneyline filtered correctly; matchup cards expanded into the selected category's full breakdown.
- Glossary search, human-readable explanations, responsive desktop/mobile flow, and global theme changes were verified. Theme selection changes the app-wide token set, not a few isolated controls.
- The verified flows produced no browser-console errors and no OpenRouter traffic; UI data calls stayed on loopback.

Visual evidence: [overview/theme](C:/src/engine/dummy/output/playwright/final-live-readiness/overview-amber.png), [Model Arsenal](C:/src/engine/dummy/output/playwright/final-live-readiness/model-arsenal.png), [WNBA Moneyline filter](C:/src/engine/dummy/output/playwright/final-live-readiness/wnba-moneyline-filter-expanded.png), [named MLB prop and expanded matchup](C:/src/engine/dummy/output/playwright/final-live-readiness/mlb-prop-filter-named-expanded.png), [expanded prop card](C:/src/engine/dummy/output/playwright/final-live-readiness/mlb-prop-expanded-card.png), and [glossary search](C:/src/engine/dummy/output/playwright/final-live-readiness/glossary-search-brier.png).

### Test-pollution incident and repair

An apparent empty daily slate during final UI QA was traced to test pollution, not a live-ingestion failure. A fixture-backed `PredatorBrain` could use the module-level production `BOARD_PATH` and replace the real board with a one-row synthetic artifact. A representative earlier one-row occurrence remains at [bet_board.test-contaminated.20260721.json](C:/src/engine/dummy/runtime/autonomy/bet_board.test-contaminated.20260721.json). The transient July 22 payload was overwritten before it could be preserved; an attempted copy was independently verified as a normal 3,976-row board and therefore is not treated as pollution evidence. That retired snapshot remains recoverable from Git history at the pre-consolidation commit `ef0d28c`.

The pytest autouse fixture now redirects `BOARD_PATH` to each test's temporary directory, and regression tests assert isolation and player-name preservation. The production board was rebuilt and browser-reverified, and later scheduled cycles have continued refreshing it normally. The isolation is in [tests/conftest.py](C:/src/engine/dummy/tests/conftest.py) and the fallback logic is in [autonomy/bet_board.py](C:/src/engine/dummy/autonomy/bet_board.py).

## Validation record

- Final repository-wide run after the attestation-freshness and unknown-phase authority repairs: **7,063 passed, 1 skipped in 665.54 seconds**. Pytest itself completed successfully.
- The outer integrity wrapper then detected that the production board had changed during the long run. Artifact inspection showed a normal scheduled 4,042-row `cycle_artifact`, generated at 07:26 local with all expected league/crypto groups—not a one-row test payload. The wrapper therefore exited nonzero after pytest solely to flag concurrent external mutation.
- With scheduled workers quiesced immediately afterward, focused board-isolation/player-name validation passed **16/16**, and SHA-256 remained `514A963A0A96A76EE98ABF317BCCA26419F5926865614C5F6718DFCE901AA96B` before and after.
- Ruff across the changed/untracked Python scope: passed.
- Python compile checks: passed.
- `git diff --check`: no whitespace errors.
- React/Vite production build: passed (65 modules).
- Production asynchronous model-provider traffic during pytest: blocked by the transport interlock.
- Live provider traffic: only the explicit four-call redacted smoke described above.
- Live-order submissions by this audit: zero.

## Blocking conditions before any capital can be risked

1. Fresh realized and walk-forward performance is negative.
2. There are zero readiness/promotion candidates; the three edge scopes are narrow and unconfirmed forward.
3. Strict sports evidence has no eligible point-in-time season and therefore no untouched holdout result.
4. Crypto evidence still has a bounded reconciliation backlog and insufficient independent, forward settlements across every requested horizon.
5. Model-weighted forecasts have not yet demonstrated incremental held-out value over quant-only forecasts after fees, slippage, and selection effects.
6. Live submit is off, model paid calls are locked, category/caps authority is not registered for trading, and no exact live-order authorization has been given.

## Next proof plan

1. **Sports data truth:** collect multiple seasons with immutable received-at, result-available-at, injury, lineup, odds, and market-close timestamps; train on earlier seasons and consume the sealed holdout once.
2. **Forward edge qualification:** shadow the three candidate scopes prospectively with event-clustered uncertainty, calibration, CLV, fee, liquidity, and adverse-selection accounting. Quarantine all seven negative scopes.
3. **Model incremental-value trial:** compare quant-only and model-weighted forecasts on identical forward cohorts. Promote model influence only if it improves Brier/log loss and after-cost shadow P&L out of sample without weakening calibration.
4. **Crypto horizon maturation:** drain the persistent settlement backlog through bounded rotations and require independent forward evidence for `15m`, `1h`, `1d`, and `1w`, rather than repeated contracts from one event cluster.
5. **Entry/exit execution proof:** accumulate confirmed shadow taker fills with contemporaneous book depth, latency, fees, partial-fill truth, adverse selection, and realized exit quality. Do not substitute submitted orders or mark-to-model returns.
6. **Canary only after gates pass:** require a fresh positive receipt-bounded backtest, positive forward shadow evidence, stable calibration, registered caps, kill-switch proof, and a new explicit operator authorization for the exact external action. Start with a separately reviewed, tightly capped canary; scale is a later gate.

## Final conclusion

Dummy is no longer merely a science experiment: it has a capable model arsenal, guarded research machinery, execution-truth controls, bounded learning loops, and a polished operator surface. What it does **not** yet have is verified, durable, after-cost edge sufficient to justify real-money operation. The elite move now is disciplined evidence collection and selective promotion—not turning off the safeguards or betting every market.

No existing Desktop audit was overwritten. No commit or push was performed as part of this report.
