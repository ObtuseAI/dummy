# DUMMY vNext Phase 2 agentization

Status: **COMPLETE_VALIDATED**

Phase 2 introduces a deterministic research-agent control plane without wiring
it into the active forecasting or execution paths. All contracts remain
`EXPERIMENTAL_SOVEREIGN_FORECASTING`, inactive after construction, and below
the constitutional `SIMULATE` ceiling.

## Delivered control plane

- `contract.py`: immutable versioned role, vertical, market, schema, clock,
  authority, evidence, fail-closed, budget, calibration, family, dependency,
  freshness-lease, and maturity declarations.
- `registry.py`: unique IDs, missing-dependency rejection, cycle rejection,
  deterministic topological order, and family/calibration grouping.
- `lifecycle.py`: `REGISTERED -> WARMING -> READY -> ACTIVE` with explicit
  `DEGRADED`, `ABSTAINING`, `QUARANTINED`, and irreversible `RETIRED` states.
  Quarantine release requires reviewed authorization.
- `mailbox.py`: typed-envelope-only delivery, deterministic sequence and IDs,
  exact sender/output and recipient/input permissions, duplicate rejection,
  and active-only delivery.
- `permissions.py`: exact input/output message types and authority checks.
- `health.py`: deterministic stale-lease, failure, invalid-output, degradation,
  abstention, and quarantine evaluation.
- `runtime.py`: dependency-gated activation, evidence and freshness checks,
  policy/market identity isolation, payload/message budgets, sanitized failures,
  explicit abstention, persistent mailbox, and reviewed recovery.

## Incumbent adapter catalog

The canonical persisted catalog is `VNEXT_PHASE2_CONTRACT_CATALOG.json`; its
canonical digest is
`55d4ba6888dfe3fe03d27136090b06d6e8149d92cc4fc76a4e4728f3d402409e`.

| Agent | Role | Clock | Output | Maximum authority |
|---|---|---|---|---|
| `btc-market-prior-v1` | market prior | 15 minute | forecast | `FORECAST` |
| `btc-incumbent-specialist-v1` | crypto specialist | 15 minute | forecast | `FORECAST` |
| `mlb-incumbent-specialist-v1` | MLB specialist | pregame | forecast | `FORECAST` |
| `btc-calibrator-v1` | proposal-only calibrator | 15 minute | calibration update | `MODEL` |
| `shadow-execution-truth-v1` | simulated fill truth | settlement | fill evidence | `OBSERVE` |
| `settlement-grader-v1` | verified settlement grader | settlement | settlement | `OBSERVE` |

The adapter layer preserves incumbent probability, uncertainty, rationale, and
feature payloads on frozen fixtures. It never mutates the incumbent signal.
Calibration emits a separate proposal linked to the base forecast. Shadow fill
evidence is always labeled `simulated`, `shadow`, and `realized=false`.
Unverified settlement abstains.

## Explicit non-capabilities

- No contract has `PAPER_ALLOCATE`, `LIVE_PROPOSE`, or `EXECUTE` authority.
- Runtime construction performs no fetch, model call, credential lookup,
  ledger mutation, activation, order construction, or broker contact.
- `dummy/agents` imports no credential, broker, live-firewall, proof-authority,
  or execution module.
- The active incumbent signal registry, weights, promotion files, caps,
  live-submit state, and scheduled tasks are unchanged.
- Phase 3 organism orchestration is not claimed by this slice.

## Acceptance evidence

- focused contract, lifecycle, registry, mailbox, runtime, health,
  import-boundary, and incumbent-adapter tests: **39 passed**;
- complete autonomy family: **1,134 passed**;
- firewall/live-cap/order-bypass family: **230 passed**;
- repository-wide Ruff: **all checks passed**;
- full repository suite: **5,585 passed in 399.94 seconds**;
- `git diff --check`: **passed**.

This evidence proves the Phase 2 contract and regression boundary. It does not
prove Phase 3 organism quality, any performance claim, or readiness for capital.
