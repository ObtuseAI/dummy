# Dummy ascendancy evidence matrix

**Snapshot:** 2026-07-26T07:38:15Z
**Base commit:** `ef0d28cd8d536c9350b05eb5ec30d979b16513bd`
**Worktree:** `C:\Users\chris\.codex\worktrees\dummy-elite-readiness`
**Authority:** research, simulation, observation, and validation only

## Verdict

| Axis | Result | Evidence |
|---|---|---|
| Engineering hardening | PASS | Full and CI-equivalent suites pass; static, dependency, package, and protected-authority checks pass. |
| Crypto/sports observation | PASS AS CONTRACT | Closed-candle crypto MCP, point-in-time sports lake, immutable artifacts, provenance, and fail-closed consumers are implemented. |
| Recursive improvement | PASS AS RESEARCH CONTRACT | Candidates can be generated, replayed, compared, rejected, and retained without self-promotion or execution authority. |
| Positive executable edge across every scope | FAIL / NOT DEMONSTRATED | Corrected family-wise replay confirms zero positive-edge scopes; direct filled-decision evidence is negative; many horizons and leagues are insufficient or absent. |
| Live-broker readiness | NO-GO | Execution/capital authority was not widened. No broker, credential, order, cancel, reconciliation, caps, or authority mutation occurred. |

Dummy is materially smaller, safer, more observable, and harder to fool. It is
not truthfully describable as profitable across every market or ready for
unsupervised live capital. Negative and insufficient scopes now abstain or stay
quarantined instead of being tuned on the same evidence until they appear
positive.

## Accepted production mutations

| Surface | Mutation | Enforced result |
|---|---|---|
| Statistical claims | Exact/approximated one-sided cluster sign tests plus Holm-Bonferroni family-wise control | A pointwise-positive interval cannot enter the edge headline without a complete test family and corrected rejection. |
| Recalibration | Chronological, canonical-event and overlapping-settlement atomic splits; equal-cluster paired bootstrap | Adoption needs at least 500 markets, 20 independent clusters, and a deterministic CI95 lower bound above zero. Repeated correlated contracts cannot manufacture adoption. |
| Backtest economics | `chal-*` outcomes separated into a modeled challenger lane | Modeled challenger PnL cannot inflate realized/fill-conditioned production PnL. |
| Candidate replay | Fill/PnL inheritance requires identical action, side, entry price, and valid positive fill count | A mutated candidate cannot inherit the incumbent's economics after changing the trade. |
| Evolution | First attributed out-of-sample genome is frozen; later fold winners are diagnostic | Per-fold leader swapping cannot leak test information into a claimed candidate. |
| Crypto point-in-time | One deep, hashed, cycle-owned snapshot; every registered/nested source rebound to it; mutation quarantine | Providers and provenance see the same immutable state. Supplied replay state can never fall through to a live fetch. |
| Crypto time | Spot/EWMA horizon and scheduled-event clocks bind to the explicit/captured cutoff | A replay is invariant to today's wall clock. |
| Crypto contracts | Central finite, positive, ordered strike-geometry preflight | Malformed contracts reject before source hooks or network reads. |
| Candle evidence | Open/close/receipt/interval/closed validation for minute, five-minute, hourly, and daily rows | Open, future, early-received, or malformed candles cannot score. |
| Sports features | Per-feature `source_available_at` and `received_at`, with no legacy backfill | Unknown-arrival or late boxscore features cannot leak into historical decisions. |
| Sports holdout | Permanent `(league, season, model)` one-shot lock with content, outcome, selection, and manifest hashes | Late games or corrected results cannot reopen a consumed holdout. |
| Sports live models | WNBA in-progress abstention, NHL regulation-tie total correction, MLB interleaved-half/walkoff/extra-inning simulation | Unsupported live state abstains; known sport-structure errors are removed. |
| Lines and parlays | True elapsed-time velocity; future/post-commence rejection; typed identity/outcome/exclusivity semantics | Text is never parsed into false independence; contradictions are zero-probability and duplicates collapse. |
| Execution tournament | Takers use the exact side-specific displayed ask plus fee; missing ask abstains | C1/C2/C4 are modeled counterfactuals; C3 is observed-fill censoring. C1-C4 cannot unlock promotion or policy switching. |
| Operator proof | Real-broker, non-fixture, single-order receipt required; submit does not synthesize fill/reconciliation | Fixture PASS or a submission receipt cannot unlock downstream operator state. |
| Observer artifacts | Canonical content rehash, request-bound `LATEST`, freshness, partial/failure precedence | Tampering, path swapping, stale data, or a newer failed observation surfaces explicitly. |

## Bounded replay and live-evidence truth

### Profitability

The 2026-07-22 full backtest artifact was replayed through the corrected
`NO_EDGE_MAP` logic without writing live runtime state:

| Classification | Scopes |
|---|---:|
| Family-wise confirmed positive edge | **0** |
| Significantly negative | 23 |
| No demonstrated edge | 74 |
| Insufficient evidence | 207 |

The old artifact contains eight pointwise-positive scopes. Its sign-test family
is absent, so the new gate correctly marks the family incomplete and confirms
none of them. This rejects a favorable but statistically unsupported result; it
does not erase those scopes from future prospective testing.

A read-only query of the continuously changing live ledger at approximately
07:38Z produced:

| Evidence lane | Graded filled decisions | Net PnL | Recorded stake | ROI | Authority |
|---|---:|---:|---:|---:|---|
| Non-challenger | 38 | **-$6.03** | $25.96 | **-23.23%** | Observational/shadow; all rows have `broker_contacted=0` |
| `chal-*` modeled challenger | 1,502 | +$118.51 | $998.04 | +11.87% | Modeled only; all rows have `broker_contacted=0`; excluded from realized production PnL |

The latest backtest summary was generated at 06:15Z and is already a stale
snapshot of that moving ledger. It reports data-quality `FAIL`: 100,000
duplicate grains, seven retained-but-excluded post-settlement rows, and 38,313
quarantined invalid-mode attempts. Its older execution-tournament headline
also treated modeled taker cohorts as promotion-ready. The corrected code
invalidates that interpretation; the artifact must be regenerated before use.

A bounded corrected tournament replay against the verified 04:35Z backup
separates descriptive sample size from authority. C1 and C4 meet the descriptive
cluster-count threshold but are `modeled_counterfactual`; their `gate_met`,
promotion-readiness, witnessed-fill, and policy-switch fields are all false.
C2, C3, and C0 are also below the sample threshold. The resulting headline has
no leading promotion cohort and reports both promotion-review and policy-switch
sufficiency as false.

### Digital assets

Direct read-only counts from `crypto_horizon_evidence.db` at approximately
07:35Z are below. Forecast rows are correlated source emissions; event clusters
are the decision unit.

| Asset | Horizon | Settled emitted forecasts | Event clusters | Disposition |
|---|---:|---:|---:|---|
| BTC | 15m | 1,299 | 120 | Evaluation-capable; not ROI proof |
| BTC | 1h | 274,393 | 74 | Evaluation-capable; not ROI proof |
| BTC | 1d | 58,697 | 3 | Insufficient independent events |
| BTC | 1w | 38,566 | 1 | Insufficient independent events |
| ETH | 15m | 1,556 | 120 | Evaluation-capable; not ROI proof |
| ETH | 1h | 353,640 | 76 | Evaluation-capable; not ROI proof |
| ETH | 1d | 8,202 | 3 | Insufficient independent events |
| ETH | 1w | 7,406 | 1 | Insufficient independent events |
| SOL | 15m | 1,397 | 122 | Evaluation-capable; not ROI proof |
| SOL | 1h | 303,949 | 75 | Evaluation-capable; not ROI proof |
| SOL | 1d | 29,598 | 3 | Insufficient independent events |
| SOL | 1w | 17,437 | 1 | Insufficient independent events |

The 06:15Z current-policy artifact has 15,832 forecasts across 762 clusters and
a small Brier advantage versus its bound market baseline (`+0.000787`), but its
mean assigned after-fee edge is negative (`-0.03548`, about -3.548 cents per
contract) and its realized filled sample is zero. A broader strict
walk-forward trade simulation was also negative: 6,661 modeled trades, 1,196
clusters, -$25.37, and -0.64% ROI. No crypto horizon is promoted.

### Sports

Historical point-in-time Glicko performance is a predictive sanity check
against a 0.25 coin-flip Brier baseline, not a market, fee, fill, or ROI test:

| League | Games | Glicko Brier | Advantage vs 0.25 | Economic disposition |
|---|---:|---:|---:|---|
| MLB | 7,651 | 0.24923 | +0.00077 | No executable edge claim |
| WNBA | 3,836 | 0.24536 | +0.00464 | No executable edge claim |
| NFL | 4,349 | 0.24693 | +0.00307 | No current-policy fill evidence |
| NHL | 16,577 | 0.24852 | +0.00148 | No current-policy fill evidence |
| NCAAF | 9,040 | 0.24026 | +0.00974 | No current-policy fill evidence |
| NCAAM (`NCAAMB`) | 102,900 | 0.23600 | +0.01400 | No current-policy fill evidence |

The current-policy artifact has only 25-46 independent MLB clusters per market
type, two to five WNBA clusters per market type, negative assigned after-fee
edge, and zero realized fills. NFL, NHL, NCAAF, and NCAAM have no current-policy
economic sample. The MLB 2025 sealed-holdout attempt found 5,495 candidate
games but zero eligibility because historical feature availability was
unknown; the holdout was correctly not consumed.

## TradingView-equivalent observer decision

[TradingView's official support page](https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/)
states that it does not currently provide an API for its data or indicator
values; its REST API is for broker integration. The reviewed community
repositories use unofficial scanner endpoints, desktop Chrome-debug access,
or scraper libraries. None was copied into Dummy's trusted runtime.

Dummy instead implements `dummy-market-observer`, a local standard-input/output
MCP with:

- closed Coinbase candles for BTC, ETH, and SOL;
- locally computed indicators, volume anomalies, support/resistance context,
  and candlestick patterns;
- immutable raw and normalized content-addressed receipts;
- local Lightweight Charts visualization;
- source rights/terms metadata, rate limits, a circuit breaker, and an
  exact-host allowlist;
- seven facts-only tools: candles, snapshot, indicators, patterns, chart
  bundle, network metrics, and source health.

Network/fundamental metrics remain `UNAVAILABLE` until a reviewed provider is
approved. The observer never scrapes or fabricates them and has no order,
allocation, promotion, amend, or cancel authority.

## Rejected optimization paths

| Rejected path | Reason |
|---|---|
| Tune every scope until historical ROI becomes positive | Reuses the test set, guarantees selection bias, and cannot create future edge. |
| Count thousands of correlated contracts as independent evidence | Artificially narrows uncertainty; event clusters are the unit. |
| Promote modeled taker economics | No witnessed fills; displayed-ask replay remains a counterfactual. |
| Use fixture proof as broker proof | A fixture cannot establish fill, reconciliation, or repeat-session readiness. |
| Clone an unofficial TradingView scraper into production | Unreviewed endpoint rights, provenance, security, and stability. |
| Force live authority, capital, or order submission | Outside this implementation's evidence and operator-authority boundary. |

## Validation

| Gate | Result |
|---|---|
| Integrated hardening selection | 396 passed |
| Crypto selection | 185 passed |
| Execution/dashboard selection | 64 passed |
| Sports point-in-time selection | 53 passed |
| Full suite, no coverage instrumentation | 5,011 passed, 85 skipped |
| CI-equivalent full suite + line coverage | 5,010 passed, 86 skipped, 216 warnings; **85.01659096034277%** over 62,082 statements |
| Ruff / compileall / `git diff --check` | PASS |
| Frozen dependency sync and consistency | 91 packages; PASS |
| Vulnerability / license policy | 0 known vulnerabilities; 87 licenses inventoried; 20 direct policies PASS |
| Package build | Wheel 2,233,737 bytes / 630 entries; sdist 2,783,284 bytes / 1,180 entries |
| Retired paths in either package | 0 Android/mobile/APK, React frontend, Qt/PySide, archive, or `predator_mesh/vNN` |
| Protected worktree authority/config changes | 0 across nine tracked protected files |

The suite emits pre-existing resource/deprecation warnings, chiefly unclosed
SQLite test handles. They do not fail the configured gate but remain cleanup
work.

## Next evidence loop

1. Regenerate the full backtest and tournament artifacts with this code so
   challenger separation, side-specific ask pricing, sign tests, and authority
   labels are present in the artifacts themselves.
2. Freeze one preregistered candidate, primary endpoint, scope family, cost
   model, and stop rule before observing the next result.
3. Collect point-in-time, cluster-atomic prospective evidence. Use 300
   independent event clusters as the default power target; never substitute
   correlated contracts for missing events.
4. Require positive after-fee ROI and Brier/CLV agreement, bounded drawdown,
   complete provenance, negative-control survival, and a family-wise corrected
   positive lower confidence bound.
5. Run an independent witnessed-fill shadow campaign. Any broker demo remains
   operator-authorized, capped, single-order, and separately reconciled.
6. Promote only through human-reviewed governed adoption. Failed or
   insufficient scopes remain abstained, are diagnosed, and receive a new
   preregistered candidate rather than a retrospective threshold edit.
