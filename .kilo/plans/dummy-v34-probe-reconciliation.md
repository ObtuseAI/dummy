# DUMMY V34 Implementation Plan

## Goal

Implement milestone `DUMMY_V34_OPERATOR_ENABLED_PROBE_RUN_RECONCILIATION_AND_LIVE_SCORE_CLOSURE_V1` as a controlled evolution of V33. V34 reuses the V33 exact operator gate (`DUMMY_PUBLIC_PROBE_MODE=1` + `DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY`), runs a bounded read-only public probe pass only when the gate is present, reconciles probe outputs through domain-specific reconcilers into a live evidence ledger, joins evidence to settlement rules, attempts due forecast closure, seeds live scores only from valid observed live-public outcomes, and produces all required V34 artifacts/reports, dashboard endpoints, safety invariant checks, and regression tests.

Expected default outcome: **PARTIAL** because the gate is disabled by default; all degraded states must be explicit and proof-backed, with no execution bridge introduced.

## Repository

`C:\src\engine\dummy`

## V33 Baseline

- `predator_mesh/v33/run.py` defines exact gate `ExactGateAcknowledgementHardeningV3`, `MinimalLivePublicProbeExecutionV1`, domain probe result helpers, evidence ingestion, settlement join, due observation, live score, calibration, cache, audit, sports exclusion, source truth, controller, and `build_default_v33_state`.
- `predator_mesh/v33/reports.py` defines `V33ReportFactory`, required report manifest, per-component payloads, dashboard report, and mission state report v19.
- `dashboard/backend/v33_routes.py` exposes `/api/v33/...` endpoints.
- `scripts/generate_v33_reports.py` writes report bundle, `final_report_v33.json`, and updates `tests_summary.json`.
- Shared helpers in `predator_mesh/v31/probes.py` provide gate primitives, fake/real transports, runner, packets, normalization, closure/score seeding. `CAPS_HASH` and `LIVE_SUBMIT_HASH` are anchored there.

## Files to Create (new V34 module)

### Core logic & state

1. `predator_mesh/v34/__init__.py`
   - `MILESTONE = "DUMMY_V34_OPERATOR_ENABLED_PROBE_RUN_RECONCILIATION_AND_LIVE_SCORE_CLOSURE_V1"`

2. `predator_mesh/v34/run.py`
   - Reuse V33 gate by importing `ExactGateAcknowledgementHardeningV3` from `predator_mesh/v33.run` and alias/export as V4 classes.
   - `PublicProbeTransportGuardV1` with modes `FAKE`, `REAL_READONLY`, `NONE`.
   - `BoundedReadonlyPublicProbePassV2` using V31 `ExplicitPublicProbeOperatorGateV3` + `V30AdapterPublicProbeRunnerV1` + selected transport guard. Gate disabled => no transport.
   - Domain reconcilers: WeatherObservationReconciliationV2, CryptoPriceReconciliationV2, PublicEventReferenceReconciliationV2, KalshiReadonlyRuleReconciliationV2.
   - `LiveEvidenceReconciliationLedgerV1`, `SettlementJoinReconciliationV4`, `DueForecastClosureReconciliationV7`, `LiveScoreClosureReconciliationV5`, `LiveCalibrationReconciliationV5`.
   - `ProbeRunArtifactReconciliationCacheV4`, `ReconciledProbeAuditLedgerV3`, `SportsProbeExclusionRecheckV5`, `SourceTruthProbeReconciliationV15`.
   - `V34OperatorEnabledProbeRunReconciliationControllerV1` (top-level).
   - `V34PartialReductionLedger`, `ProbeReconciliationSprintQueueV11`, `ProbeReconciliationToScoreCompoundingControlPlaneV18`, `DomainMarketClassScoreboardV19`.
   - Runtime budget classes.
   - `build_default_v34_state(enable_network=False, env=None)` wiring components in truth-spine order.

3. `predator_mesh/v34/reports.py`
   - Mirror V33 reporting structure for V34.
   - `DEFAULT_REQUIRED_REPORT_NAMES` with ~186 names.
   - `V34ReportFactory`, dashboard report v1, mission state report v20.

### Dashboard routes

4. `dashboard/backend/v34_routes.py`
   - `APIRouter(prefix="/api/v34", tags=["v34"])` with 22 endpoints.

### Report generator script

5. `scripts/generate_v34_reports.py`
   - Writes all required reports, `final_report_v34.json`, updates `tests_summary.json`.

### Tests

6. `tests/v34_test_helpers.py`.
7. ~130 `tests/test_v34_*.py` files covering classes and safety invariants.

## Safety Invariants

Reports must include:

- `live_submit_disabled=true`, `caps_unchanged=true`, `execution_bridge_present=false`.
- `secret_values_exposed=false`, `source_api_keys_exposed=false`, `github_tokens_exposed=false`, `kalshi_private_keys_exposed=false`, `llm_secrets_exposed=false`.
- `order_endpoints_used=false`, `cancel_endpoints_used=false`, `private_endpoints_used=false`.
- No browser/PageAgent/dom/mined repo additions.
- No fixture/dry run/sample/stale cache/probe failure/disabled probe scoring.

## Default Expected Values (no gate)

- `gate_state=DISABLED_BY_DEFAULT`, `exact_ack_validation_status=FAIL_MISSING_ACK`, `gate_enabled=false`.
- `probe_run_count=0`, `source_family_count=4`.
- `live_evidence_count=0`, `settlement_compatible_evidence_count=0`.
- `due_forecast_count=4`, `observed_forecast_count=0`, `live_scored_count=0`, `live_unresolved_count=4`.
- `sports_source_mode=FIXTURE_REPLAY_ONLY`.
- Verdict: **PARTIAL**.

## With Exact Gate

- `gate_state=ENABLED_READONLY_PUBLIC_PROBES`, `exact_ack_validation_status=PASS`, `gate_enabled=true`.
- `probe_run_count=3`, `live_evidence_count=3`, `settlement_compatible_evidence_count=3`.
- `observed_forecast_count=3`, `live_scored_count=3`, `live_unresolved_count=1`.
- Verdict remains **PARTIAL** due to Kalshi + sports blockers.

## Required Reports

All 186+ named reports plus `dummy_mission_state_report_v20.json`, `dashboard_v34_report_v1.json`, `v34_runtime_budget_report_v1.json` and children. Index artifacts: `final_report.json`, `tests_summary.json`, `final_report_v34.json`.

## Dashboard Integration

Import and register `dashboard/backend/v34_routes.py` in `dashboard/backend/main.py`.

## Regression Steps

1. `python -m py_compile predator_mesh/v34/reports.py scripts/generate_v34_reports.py dashboard/backend/v34_routes.py`
2. `python scripts/generate_v34_reports.py`
3. `python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60`
4. `python -m pytest tests/ -q --tb=short --timeout=60`
5. `cd dashboard/frontend && npm run build`
6. Re-run V8–V33 report generators.

## Backwards Compatibility

Keep V31–V33 modules, report names, tests, routes, and hashes intact. Do not modify `configs/live_submit.json`, `configs/caps.json`, or canonical Blunder identity.

## Operator Actions

- Set `DUMMY_PUBLIC_PROBE_MODE=1` and `DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY` to enable bounded read-only public probes.
- Review Kalshi READ_ONLY access and sports source terms.
- Leave live-submit and caps unchanged.
