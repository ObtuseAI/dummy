# Dummy elite-readiness implementation

**Implementation date:** 2026-07-26
**Source plan:** `DUMMY_LAUNCH_PLAN_2026-07-26.md`
**Base commit:** `ef0d28cd8d536c9350b05eb5ec30d979b16513bd`
**Implementation branch:** `agent/dummy-elite-readiness`

## Outcome

The safe code-hardening boundary of the program is implemented. Full live
launch is **BLOCKED**, and Phase 1.4 remains explicitly blocked on a safe
transaction design rather than shipping the reviewed overwrite race.
Dummy has a smaller maintained surface, stronger evidence and authority
boundaries, a supervised operations plane, a rights-aware crypto observation
MCP, and a single read-only operator board. It has not earned the operational
or statistical evidence required to widen live scope.

No implementation step:

- armed live submission;
- edited caps or operator-authority material;
- placed, amended, cancelled, or reconciled an order;
- contacted a broker;
- promoted a challenger or execution policy;
- treated a chart, model claim, backtest, or research result as capital
  authority.

## Deliberate plan refinements

Some plan wording was made safer rather than copied literally:

1. The canonical dashboard is loopback-only and GET-only. The retired React,
   Android, Qt, legacy FastAPI, and tailnet control surfaces were removed.
   Token-gated mutation and guided arming were not moved into the board because
   that would turn a hardened observer back into an authority-writing surface.
2. The market-observation service does not scrape TradingView. TradingView
   documents that it does not expose an API for obtaining its market data or
   indicator values. Dummy instead uses a reviewed public candle provider,
   computes indicators and candlestick patterns locally, and renders immutable
   bundles with the official Apache-2.0 TradingView Lightweight Charts library.
3. Historical `predator_mesh/vNN` source and the repository archive were
   removed from the maintained tree, not moved into another tracked archive.
   Their evidence contracts were consolidated and hash-parity checked; Git
   remains the recovery mechanism.
4. No signal downsampling was applied merely to hit a numeric reduction target.
   A read-only production sample showed that deleting every fused row would
   reduce the measured row count by only about 1.17 times, not 10 times, while
   destroying gradeable evidence. Writes were batched without silently
   discarding observations.
5. Backup creation uses SQLite `VACUUM INTO` under a cooperative backup lease
   rather than a restart-prone application-level page-copy loop. Publication
   is atomic and occurs only after hashes, `quick_check`, table-count parity,
   and a restored-copy drill succeed.

## Plan disposition

`COMPLETE` means the code contract is implemented and locally validated.
`PARTIAL` means code was delivered but the plan's operational done-criterion
still needs real elapsed evidence. `BLOCKED` means evidence or operator
authority is absent; it is not a request to loosen the gate.

### Phase 0 — stop the bleeding

| Item | Status | Implementation and remaining evidence |
|---|---|---|
| 0.1 retention contention | PARTIAL | Cooperative dead-PID-safe leases, bounded SQLite retry, eligibility indexes, scan budgets, and truthful `APPLIED`/`REFUSED` receipts are implemented. The 06:03Z UI-validation capture showed the live receipt as `REFUSED`; a successful live retention plus size reduction is still required. |
| 0.2 supervised launchers | PARTIAL | All maintained VBS launchers wait for their child and propagate its exact exit status. A typed job registry and no-shell supervisor add lock groups, timeouts, and receipts. Task Scheduler registration and observed `LastTaskResult` remain operator-host validation. |
| 0.3 vacuum | PARTIAL | Vacuum now requires a recent restore-verified backup and a cooperative maintenance lease; it never kills or disables tasks. Log-content watchdog coverage is present. The first successful live vacuum and freelist reclamation remain unproven. |
| 0.4 clean live state | BLOCKED | The implementation did not rewrite the operator's existing live-submit/caps/authority work or stop a live process. The final 06:32Z independent validator reported `configs/live_submit.json:not_default_disabled_for_readiness_review`, while the persisted dashboard snapshot reported a disabled authority state; that mismatch must be reconciled through the operator runbook. |
| 0.5 authority-state tests | COMPLETE | Tests use the canonical disarmed/validly-armed state classifier, include a positive valid-arm fixture, and preserve the independent session, kill, caps, and per-order gates. |
| 0.6 contention regression | COMPLETE | Lock-deadline, retry, truthful refusal, lease, and launcher exit propagation have regression coverage. |
| 0.7 one-off backup | COMPLETE | `C:\DummyBackups\backup-20260726T043513.401206Z` was atomically published after both copied databases passed SHA-256 verification, SQLite `quick_check`, table-count parity, and restored-copy drills. The verified files are `ledger.db` (23,247,962,112 bytes) and `signals_archive.db` (4,900,397,056 bytes); the directory contains only those files and `manifest.json`. |

### Phase 1 — operational integrity

| Item | Status | Implementation and remaining evidence |
|---|---|---|
| 1.1 external critical alerts | PARTIAL | Opt-in HTTPS delivery uses an exact host allowlist, port 443, no redirects, no local/private targets, redacted payloads, redacted receipts, and a test network guard. A real staged phone receipt is still required. |
| 1.2 content-aware watchdog | COMPLETE | The watchdog parses bounded job receipts, lets a latest `REFUSED` override fresh mtime, tracks last successful stamped `APPLIED`, and detects 48-hour research stalls by active cohort. |
| 1.3 write-volume reduction | PARTIAL | Raw signals and picks are phase-batched with bounded chunks so other writers can interleave. The requested 10-times row reduction was not evidence-safe or supported by the observed row composition; cycle-time improvement remains to be measured live. |
| 1.4 atomic learner writes | PARTIAL / BLOCKED | The original per-write fail-fast behavior is preserved. An attempted absolute-weight buffer was removed after review proved it could overwrite a concurrent update. Safe completion requires discovery without claiming, pre-claim point-in-time signal lookup, ordered semantic weight events, a genuinely short `BEGIN IMMEDIATE`, and claim/grade/guard in one transaction. |
| 1.5 signal-generation N+1 | PARTIAL | One coherent cycle weight snapshot is injected into the forecaster. The pre-change runtime was about 152 seconds; the target of less than 60 seconds still requires a live cycle measurement. |
| 1.6 WAL discipline | PARTIAL / CURRENTLY FAILING | `wal_autocheckpoint`, passive idle checkpointing, WAL/SHM metrics, and watchdog thresholds are explicit. The 2026-07-26 06:03Z UI-validation capture reported a 21.784-GiB ledger, a 7.68-GiB WAL, and a ledger threshold of 18.63 GiB, so the operational gate was failing; these live values are point-in-time and the required seven days below threshold remain unproven. |
| 1.7 adaptive deadline | PARTIAL | The deadline follows trailing healthy phase p95 plus a margin, and low margin is surfaced. A week without false deadline alerts remains unproven. |
| 1.8 heartbeat preservation | COMPLETE | An error cycle preserves last healthy counts and success time instead of null-clobbering them. |
| 1.9 backup cadence | PARTIAL (1/7) | One off-volume online backup and restored-copy drill is verified. Free-space and distinct-volume gates are enforced. Scheduler installation and six more consecutive daily verified snapshots remain operator-host work. |

### Phase 2 — operator truth

| Item | Status | Implementation and remaining evidence |
|---|---|---|
| 2.1 money truth | COMPLETE | The misleading Android and Qt surfaces were deleted. The canonical board reads the live account snapshot and reports capture age and authority state. |
| 2.2 one surface | COMPLETE | The React frontend, Android app, Qt tote, legacy dashboard, tailnet launchers, and dead dashboard launchers were removed. `autonomy.dashboard` on loopback port 8787 is canonical. |
| 2.3 system health | COMPLETE AS CONTRACT | The read-only board renders validated watchdog/heartbeat/freshness, bounded alert and recent-cycle history, ledger/WAL/retention/deadline/promotion evidence, and explicit unavailable states. The 06:03Z UI-validation capture truthfully rendered `PARTIAL`: retention was `REFUSED`, `CycleDeadline` was 16/40, and per-cycle SQLite retry telemetry was unavailable. |
| 2.4 edge quality | COMPLETE AS CONTRACT | The board validates and bounds the current board artifact, renders its after-fee edge distribution, separates exact statistical evidence from caps candidacy and live authority, and withholds reasons for stale or invalid boards. The 06:03Z capture had 30 validated after-fee rows, all below zero; actionable share was explicitly unavailable because its dedicated producer receipt was absent, and maker/taker evidence was stale and audit-only. These live values are timestamped observations, not durable claims. |
| 2.5 guided arming | NOT IMPLEMENTED BY DESIGN | Arming, session mutation, start/stop, and cancellation remain shell/runbook and operator-only. The board cannot write authority. |
| 2.6 non-loopback auth | COMPLETE BY DENIAL | The maintained server rejects non-loopback peer/Host requests rather than offering a weaker remote tier. It also applies a restrictive CSP and GET-only route boundary. |
| 2.7 vocabulary | COMPLETE | `LOCKED`, `ARMED / NO SESSION`, `LIVE`, and `PENDING CANCEL AND RECONCILE` are defined in one contract and pinned across the board and readiness output. |

### Phase 3 — alpha and execution policy

| Item | Status | Implementation and remaining evidence |
|---|---|---|
| 3.1 maker/taker tournament | BLOCKED | No policy was selected. At the 06:03Z capture the replay was 91 hours stale: witnessed maker C0 had only 28 clusters and failed its sufficiency gate, while taker C1 was a counterfactual replay rather than a second realized book. Choosing either would manufacture readiness. |
| 3.2 market-prior dominance | PARTIAL | Market prior is capped at 60% when at least one other admitted source exists; prior-only forecasts remain possible. Settled shadow A/B proof that promoted sources move the traded number remains required. |
| 3.3 macro/equity scope | COMPLETE | Macro and equity-drift sources abstain at 15-minute and one-hour horizons; short-horizon promotion claims are excluded. |
| 3.4 adverse selection | PARTIAL | Fresh cluster-bootstrap fill/no-fill evidence now produces a nonnegative maker-only EV/Kelly haircut; missing, stale, malformed, or future evidence blocks maker decisions. The current report is stale, and no default policy was changed. |
| 3.5 calibrated traded path | PARTIAL | Content-bound v2 reliability maps can create a gradeable calibrated shadow. Only an exact promoted scope can alter the traded forecast, with attribution preserved for demotion. The live artifact is legacy/unbound and there are zero active fused-cal scopes. |
| 3.6 grading backlog | PARTIAL | A supervised out-of-band worker paginates public GET settlement data, requires at least 95% attempt coverage, uses the same atomic grading path, and emits receipts. Sustained live coverage at or above 0.95 is not yet proven. |
| 3.7 per-candidate Kelly | COMPLETE | Each candidate is limited by its own uncertainty-adjusted Kelly budget before portfolio-pot allocation. |
| 3.8 firewall chokepoint | COMPLETE | The firewall independently recomputes side-specific half-sigma net EV, fees, caps, and net-edge thresholds. Optimistic upstream claims cannot bypass it. Dormant execution alternatives were deleted. |
| 3.9 cancel on kill | PARTIAL | Stop truthfully enters `PENDING CANCEL AND RECONCILE` while open-order state is unproven. A separately injectable cancellation coordinator exists but is not wired to live credentials or authority. A demo kill drill remains required. |
| 3.10 strategy catalog | COMPLETE | One typed catalog reports six `RESEARCH_ONLY` and three `DORMANT` strategies, with zero execution authority. The legacy forecast engine and placeholder strategy paths were deleted. |

The audit's negative-scope fail-open defect is also closed. Missing, unreadable,
malformed, future-dated, stale, or policy-mismatched `no_edge_map` evidence now
suppresses every independent fusion source. A market-prior-only display anchor
has zero edge and 0.5 uncertainty, which the allocator must abstain on; no
market prior produces no forecast. A fresh validated map admits unaffected
sources and excludes each exact significantly negative scope.

### Phase 4 — self-improvement fuel

| Item | Status | Implementation and remaining evidence |
|---|---|---|
| 4.1 forward coverage | PARTIAL | Active-cohort issuance is tracked and a 48-hour stall is critical. The current cohort had recent issuance during the read-only check, but sustained daily coverage remains an operational measurement. |
| 4.2 honest research gates | COMPLETE | Recursive research uses typed hypotheses, deterministic canaries, leakage checks, zero-network/credential/spend workers, semantic deduplication, a hash-chained journal, and external acceptance. It cannot promote itself. |
| 4.3 fossil removal | COMPLETE | All versioned `predator_mesh/vNN` modules were removed. A content-addressed registry preserves 194 report contracts, and import boundaries prevent the fossil namespace returning. |
| 4.4 harvester lifecycle | COMPLETE | All 43 current targets are honestly `DORMANT`; zero are fabricated as verified. The only path forward is evidence-gated `VERIFIED_CHALLENGER`, which still grants no execution authority. |
| 4.5 unified status | PARTIAL | The elite validator combines operations, canary, research, scale, and authority gates into one fail-closed report. Time-to-next-research-gate estimates remain evidence-dependent rather than guessed. |

### Phase 5 — full-launch gate

The full-launch checklist is **NO-GO**. Missing evidence includes:

- 14 consecutive green operational days;
- a stamped successful retention run and proven vacuum;
- seven verified daily backups;
- a real external alert receipt;
- opt-in demo place/cancel/fill and kill-drill evidence;
- sustained grading coverage of at least 0.95;
- a maker/taker policy decision from sufficient clusters;
- fresh adverse-selection and content-bound calibration evidence;
- positive realized post-fee edge with a pre-registered window and positive
  lower confidence bound, or an explicit operator exploratory-risk decision;
- operator end-to-end runbook validation;
- mutation-testing evidence for the money gate.

The 2026-07-26 06:03Z read-only UI capture reinforces that decision: system
health was degraded, the live account observer session was expired, retention
was refused, 40% of the last 40 cycle receipts ended in `CycleDeadline`, and
the 30 then-validated board edges were all negative after fees. Exact
KXSOL15M statistical and caps-series evidence was visible but remained
deliberately separated from execution authority. These rapidly changing
runtime values are point-in-time evidence, not durable current-state claims.
The final independent elite validator at 06:32Z also detected that the operator-owned
`configs/live_submit.json` was not in the default-disabled readiness state,
despite the persisted board snapshot showing disabled authority; it therefore
kept execution authority false and required operator reconciliation. Its
operations axis remained blocked because the ledger was over threshold and the
watchdog was not healthy; forward canary, scale, and the research control-plane
artifacts were also missing. The command reported zero broker contact, zero
orders, zero credential reads, and zero runtime mutation.

## Crypto Market Observer MCP

The new `dummy-market-observer` standard-input/output MCP exposes seven
facts-only tools:

- `get_candles`;
- `get_market_snapshot`;
- `compute_indicators`;
- `detect_candlestick_patterns`;
- `get_chart_bundle`;
- `get_network_metrics`;
- `source_health`.

It allowlists BTC, ETH, and SOL at 15-minute, one-hour, four-hour, one-day, and
one-week intervals. It uses closed candles, computes indicators and patterns
locally, records immutable content-addressed observations, advances `LATEST`
only on a complete observation, and includes source rights/terms metadata.
Rate limiting, a circuit breaker, exact-host HTTPS validation, and a
cross-process lock are fail-closed.

The dashboard reads those artifacts; it never triggers a provider refresh.
Chart rendering is local. Chart output is descriptive technical evidence, not
a price prediction, fundamental claim, promotion, allocation, or order.

A bounded live smoke collected 120 closed one-hour bars for each asset and
persisted these observation digests:

- BTC: `a0805f1807f0a6422bf658d5da9a1f8d0193932676d4dc228555e5832426b06f`;
- ETH: `87be14d9c18915f65975b9177a1c97be1313312565241abe58e010191aed3687`;
- SOL: `89b2d8f0f67d804866cf6d1513bb2e151dda05a4312571d76513684828e5b8a2`.

`get_network_metrics` remains explicitly `UNAVAILABLE` until a separate
fundamental-data source passes the same rights and exact-host review. Dummy
does not fill that gap with scraping or synthetic fundamentals.

## Removed bloat

- the complete Android/mobile app;
- the React/Vite dashboard;
- the Qt desktop tote;
- the legacy FastAPI dashboard and remote/tailnet launchers;
- alternative execution packages and dead adapters;
- all tracked repository archive files;
- all `predator_mesh/vNN` source directories and their duplicate tests;
- legacy ForecastEngine/V1 parsing and 30 name-only forecasting wrappers;
- eight zero-consumer adapter stubs;
- clean merged worktrees, merged local branches, and empty worktree parent
  directories outside the repository.

Historical tracked files remain recoverable from Git at the base commit.
Material runtime/evidence directories outside the repository were preserved.

The final inventory measured 5,880 base blobs versus 1,769 effective
nonignored files: 4,111 fewer files (69.91%), with 4,195 tracked deletions.
The maintained counts for Android, mobile/tailnet launchers, the React
frontend, Qt/PySide non-test references, `archive/`, and `predator_mesh/vNN`
were all zero.

## Additional supply-chain and test isolation hardening

- `uv.lock` is the one dependency resolution; CI syncs and runs with
  `--frozen`.
- Runtime dependency floors and ceilings are explicit.
- License policy and known-vulnerability checks run in the supply-chain
  workflow.
- Ordinary pytest redirects omitted, relative-default, or project-equivalent
  `AutonomyLedger` paths to the current test's temporary directory, including
  constructor aliases imported before fixture setup. Explicit temporary
  ledgers continue unchanged.
- Recursive research workers inherit no ambient parent environment. Their
  fixed environment exposes neither network, credentials, spend, nor
  production authority.

## Ascendancy truth-hardening pass

The follow-on optimization pass hardened the research and evidence plane
without widening authority:

- cluster sign tests and Holm-Bonferroni family control now prevent pointwise
  winners from becoming edge claims;
- recalibration adoption uses canonical event/settlement-atomic splits and an
  equal-cluster paired bootstrap;
- modeled challenger outcomes are separated from realized economics;
- candidate replay cannot inherit a changed trade's fills or PnL, and one
  genome is frozen before attributed out-of-sample evaluation;
- every crypto provider now shares one immutable cycle snapshot and replay
  clock, with central contract/candle point-in-time validation;
- sports boxscore features carry their own arrival envelope, and sealed
  holdouts are permanently content-bound;
- taker cohorts use side-specific displayed asks and all C1-C4 replay lanes are
  barred from promotion/policy-switch readiness;
- fixture proof can no longer unlock broker-derived workflow state.

The detailed market, replay, mutation, and profitability disposition is in
`docs/ASCENDANCY_EVIDENCE_MATRIX_2026-07-26.md`.

Publication hardening also:

- made the lazy `EvidencePath` concrete-path compatible on Python 3.11 while
  preserving Python 3.12+ behavior;
- pinned the vendored chart renderer, license, notice, and manifest as exact
  bytes across Windows checkouts;
- retained `execution/` only as a code-free constitutionally protected
  namespace; and
- removed the unused `services` package, including its mutable report writer
  and root-level SQLite order-store duplicate.

## Validation

Final-state locked-environment validation is recorded here rather than inferred
from individual focused suites:

- frozen dependency sync/check: **PASS**, 91 installed packages compatible;
- Ruff, compileall, and `git diff --check`: **PASS**;
- full pytest without instrumentation: **PASS**, 5,011 passed and 85 skipped;
- CI-equivalent pytest and the unrounded 85% line-coverage gate: **PASS**,
  5,016 passed, 86 skipped, 215 warnings, 85.24% across 62,033 statements;
- package build: **PASS**, a 2,231,650-byte wheel (627 entries) and
  2,784,195-byte sdist (1,178 entries), with zero retired Android, archive,
  React, Qt, or `predator_mesh/vNN` paths;
- vendored JavaScript syntax/hash and dashboard evidence contracts: **PASS**,
  including 27 focused passes and one environment skip;
- license and vulnerability gates: **PASS**, 91 dependencies audited with zero
  known vulnerabilities, 87 installed licenses inventoried, and all 20 direct
  dependency policies passing;
- protected authority/config diff: **PASS**, zero worktree changes under
  `configs/live_submit.json`, `configs/caps.json`, or
  `operator_authority_pack`;
- final live read-only elite validator: **BLOCKED AS EXPECTED**, execution and
  capital authority false, zero broker contact/orders/credential reads/runtime
  mutation.

## Operator next actions

1. Preserve the protected-branch review and CI path for PR #186; do not bypass
   the dependency audit or three-version Python matrix.
2. Keep Dummy disarmed. Resolve the pre-existing live authority/config state
   only through the operator runbook.
3. Install the supervised tasks, configure an approved critical-alert
   destination, and prove one staged phone alert.
4. Install the daily backup schedule and obtain six more consecutive
   off-volume restore-verified snapshots.
5. Run retention and vacuum under normal writer load using the verified backup
   gate, then start the 14-day
   operational observation window.
6. Regenerate content-bound reliability and adverse-selection evidence, drain
   grading coverage, and let the existing evidence gates decide whether any
   challenger or execution policy deserves review.
7. Perform demo-only broker and kill drills. Do not widen capital or scope
   until every Phase-5 gate is evidenced.
