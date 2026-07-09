# V36 Exact-Operator Real Read-Only Public Probe Run and Live Sample Expansion

## Authority & goal
Repo: `C:\src\engine\dummy`. V35 = authority (PARTIAL, frontend PASS, 173 reports, 2977 passed/2 skipped). V36 bridges fake-transport proof to **exact-gated real read-only public probe** execution, preserving all V35 FAIL-escalation / no-execution-bridge invariants.

Exact gate (reused unchanged from V33/V34): `DUMMY_PUBLIC_PROBE_MODE=1` + `DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY`. Real probes run **only** when that exact gate is present in the *actual runtime env*. Normal tests/CI never set it => no live network. Degrades cleanly to PROBE_DISABLED/no-evidence/no-score (PARTIAL, proof-backed).

## Pattern: mirror V35 1:1 with V36 names
- `predator_mesh/v36/__init__.py` (MILESTONE)
- `predator_mesh/v36/run.py` — dataclasses + evaluators for all 27 objectives + `build_default_v36_state(enable_real_probe=False, real_transport=None, env=None)`
- `predator_mesh/v36/reports.py` — `DEFAULT_REQUIRED_REPORT_NAMES`, `_safe_base`/`_verdict` (reuse V35 FAIL-propagation: any `*_status=="FAIL"`=>FAIL), `_component_payload`, `V36ReportFactory`, `dummy_mission_state_report_v22`, `generate_dashboard_v36_report_v1`
- `scripts/generate_v36_reports.py` — real-env gate recheck, frontend build, v34 route smoke, write all reports + `final_report_v36.json` + refresh `final_report.json`/`tests_summary.json`; FAIL if frontend build or route smoke fails (V35 semantics)
- `dashboard/backend/v36_routes.py` — 23 `/api/v36/*` endpoints (V35 `_slice` pattern); register in `dashboard/backend/main.py` (1 import + 1 include_router). App.jsx untouched (V34/V35 precedent keeps frontend build green).
- `tests/v36_test_helpers.py` + 32 `tests/test_*_v36.py`
## Key components (objectives 1-26)
1. `V36RealProbeRunControllerV1` + input state/gate decision/execution plan/result/blocker/safety proof — consumes V35 final+mission state, rechecks exact gate at runtime, runs minimal real probe pass only if gate passes; records source families, request/response/failure counts, real evidence packets, settlement-compatible evidence, observed, real scored, unresolved; proves caps/live_submit unchanged + no order/cancel/live-submit touched + no execution bridge.
2. `ExactOperatorGateRuntimeV5` — reads `os.environ` (runtime) or passed dict (tests); exact-string `==` only; rejects fuzzy/missing/trading-language; records only safe metadata (no env dump, no secrets). Produces gate snapshot/ack decision/run decision/failure instruction/audit proof.
3. `RealReadonlyProbeTransportV1` — wraps existing `HttpJsonPublicProbeTransportV1` (`predator_mesh/v31/probes.py`); per-request + total timeout, request cap, no retry storm, source/failure-labeled; only constructed when gate passes; injectable stub for tests.
4. `MinimalRealPublicProbePassV1` — families weather/crypto/public_event/kalshi_readonly (sports excluded), max 1-2/family, total cap, bounded timeouts.
5-8. Domain real probes (weather/crypto/public_event/kalshi_readonly) — packets, settlement joins, blockers with exact codes (`SOURCE_UNAVAILABLE`,`STALE_EVIDENCE`,`METRIC_INCOMPATIBLE`,`CONTRADICTION_LOW_CONFIDENCE`,`SETTLEMENT_AMBIGUOUS`,`READONLY_ACCESS_UNAVAILABLE`). Kalshi only if read-only config sentinel present.
9. `RealLivePublicEvidenceLedgerV1` — accepts ONLY `source_mode==LIVE_PUBLIC_PROBE_RESULT` real packets; hard-rejects fake/fixture/dry-run/sample/stale/source-unavailable; full provenance fields.
10. `RealSettlementJoinV1` — family-scoped joins; validate market class/metric/role/timestamp; ambiguous=>`SETTLEMENT_AMBIGUOUS`; no scoring here.
11. `RealDueForecastObservationClosureV1` — closes due forecasts from real joins; exact blockers (`PROBE_DISABLED`,`FAIL_MISSING_ACK`,`NO_MATCHING_LIVE_PUBLIC_EVIDENCE`,`SOURCE_UNAVAILABLE`,`SETTLEMENT_AMBIGUOUS`,`STALE_EVIDENCE`,`NOT_DUE_YET`,`CONTRADICTION_LOW_CONFIDENCE`); no mutation/fabrication.
12. `RealLiveScoreSeedV1` — scores ONLY `OBSERVED_REAL_LIVE_PUBLIC`; rejects all invalid modes; low-sample warning; no PnL; no scoring-to-execution bridge.
13. `RealLiveCalibrationSeedV1` — consumes only RealLiveScoreSeedV1 outputs; separate from replay/fixture/sample/fake; preserve exact blocker when count==0; no trading-readiness claim.
14. `RealProbeArtifactCacheV1` — redacted public evidence/summaries only; freshness policy + redaction audit; no promotion.
15. `RealProbeAuditLedgerV1` — append-only-modeled gate/transport/evidence/observation/score/safety audits.
16. `FakeToRealEvidenceSeparationV1` — V35 fake-transport scores stay `PIPELINE_SCORE_ONLY`; V36 real scores separate; fake/real counts shown separately; promotion blocker.
17. `SportsFixtureOnlyRealProbeRecheckV7` — sports stays `FIXTURE_REPLAY_ONLY`; no odds scraping/wagering/undocumented endpoints; approval packet only if relevant.
18. `SourceTruthV17RealProbeAndSampleReadiness` — health/availability/usefulness/score/sample signals from real results; next action; cannot recommend live trading.
19. `V36PartialReductionLedger` — before/after known V35 partial causes; pass delta; exact operator action when gate disabled.
20. `V36RealProbeSprintQueueV13` — tasks from actual V36 state; sports legality-first; no live-trading work item; no browser/mined code.
21. `V36CompoundingControlPlaneV20` — probe/evidence/settlement/observation/score queues + next-bundle recommendation from V36 reality; preserves V35 FAIL escalation.
22. `DomainMarketClassScoreboardV21` — per market-class rows with default/fake/real columns (gate state, run/evidence/settlement-compatible/observed/scored/fake-pipeline/unresolved/sample-status/next-action).
23. `dummy_mission_state_report_v22.json` — V17/V21-V35 carried statuses + V35 FAIL-escalation-preserved flag + every V36 status line + live-submit disabled + caps unchanged + no browser/PageAgent/mined-code.
24. `dashboard_v36_report_v1.json` + 23 endpoints; show gate status/run count/transport mode/fake count separate/real evidence/real observed/real scored/fake pipeline scores/sample status/next rec/proof paths/live-submit disabled/caps unchanged/no browser/no mined repo; no secrets/keys/tokens/prompts exposed.
25. `V36RuntimeBudget` + `RealProbeRuntimeBudgetV1`/`RealTransportRuntimeBudgetV1`/`RealClosureRuntimeBudgetV1` + `DashboardCachePolicyV18` + `ReportChainRuntimeProfilerV19` — fixtures/fake transport only in unit tests; real network only if gate; `--timeout=60`; bounded total runtime; no report-chain explosion.
26. ~60 security/execution invariant reports (`no_*`,`readonly_only`,`blunder_separation_recheck_v36`,`dummy_canonical_identity_report_v36`) via V35 `_safety_payload` pattern — all PASS, no bridge, plus V36 bridge names (real_probe_run/real_transport/real_evidence_ledger/real_settlement_join/real_due_observation/real_live_score/real_live_calibration/real_probe_cache/real_probe_audit/fake_to_real_evidence_separation/source_truth/sprint_queue to execution).
## Files to create
```
predator_mesh/v36/__init__.py
predator_mesh/v36/run.py            (all 27 objectives: dataclasses + evaluators + build_default_v36_state)
predator_mesh/v36/reports.py        (DEFAULT_REQUIRED_REPORT_NAMES, _safe_base, _verdict, _component_payload, V36ReportFactory, dummy_mission_state_report_v22, generate_dashboard_v36_report_v1)
scripts/generate_v36_reports.py     (orchestrator: real-env gate recheck, frontend build, v34 route smoke, write all reports + final_report_v36.json + refresh final_report.json/tests_summary.json)
dashboard/backend/v36_routes.py     (23 endpoints)
tests/v36_test_helpers.py            (assert_v36_report_named, assert_current_test_report mapping)
tests/test_v36_real_probe_run_controller_v1.py
tests/test_exact_operator_gate_runtime_v5.py
tests/test_real_readonly_probe_transport_v1.py
tests/test_minimal_real_public_probe_pass_v1.py
tests/test_weather_real_public_probe_v1.py
tests/test_crypto_real_public_probe_v1.py
tests/test_public_event_real_public_probe_v1.py
tests/test_kalshi_readonly_real_probe_v1.py
tests/test_real_live_public_evidence_ledger_v1.py
tests/test_real_settlement_join_v1.py
tests/test_real_due_forecast_observation_closure_v1.py
tests/test_real_live_score_seed_v1.py
tests/test_real_live_calibration_seed_v1.py
tests/test_real_probe_artifact_cache_v1.py
tests/test_real_probe_audit_ledger_v1.py
tests/test_fake_to_real_evidence_separation_v1.py
tests/test_sports_fixture_only_real_probe_recheck_v7.py
tests/test_source_truth_v17_real_probe_and_sample_readiness.py
tests/test_v36_partial_reduction_ledger.py
tests/test_v36_real_probe_sprint_queue_v13.py
tests/test_v36_compounding_control_plane_v20.py
tests/test_domain_market_class_scoreboard_v21.py
tests/test_dummy_mission_state_v36.py
tests/test_dashboard_v36.py
tests/test_v36_runtime_budget.py
tests/test_no_secret_leak_v36.py
tests/test_no_direct_order_bypass_v36.py
tests/test_no_browser_automation_v36.py
tests/test_no_fake_transport_score_claimed_live_v36.py
tests/test_no_real_probe_run_to_execution_bridge_v36.py
tests/test_no_sprint_queue_to_execution_bridge_v36.py
tests/test_v35_still_passes_or_partial_expected_v36.py
```

## Files to edit
- `dashboard/backend/main.py`: add `v36_routes` to the import block (after `v35_routes`) and `app.include_router(v36_routes.router)` after the v35 line. No other changes.

## Test design (no live network)
- `build_default_v36_state` defaults gate-disabled => all real-probe counts 0, no HTTP transport.
- Gate tests pass explicit `env={...}` dicts + a **stub** `fetch_json` transport (never `HttpJsonPublicProbeTransportV1`, never `os.environ` mutation).
- `test_v36_runtime_budget` asserts `real_network_only_if_gate_enabled=True` and `unit_tests_use_fixtures=True`.

## Validation (objective 27)
1. `python -m py_compile predator_mesh/v36/reports.py scripts/generate_v36_reports.py dashboard/backend/v36_routes.py`
2. `python scripts/generate_v36_reports.py`
3. `python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60`
4. `python -m pytest tests/ -q --tb=short --timeout=60`
5. `cd dashboard/frontend && npm run build`
6. Re-run `scripts/generate_v8_reports.py` ... `scripts/generate_v36_reports.py` in order (idempotent; V8-V35 stay green).
## Verdict
Normal CI => tests pass, frontend PASS, real probe reports `PROBE_DISABLED_BY_DEFAULT`, real evidence/observed/scored=0, all blockers explicit+proof-backed => **PARTIAL** (matches V35 authority + spec PARTIAL rules). PASS reachable only when operator sets exact env gate at runtime and re-runs the generator (gated path implemented, not exercised in tests). FAIL = spec FAIL list (test/build failure, V35 FAIL-escalation regression, live-submit/caps modified, order/cancel bypass, secret leak, browser/PageAgent/DOM/mined-code lane, fake-transport score claimed live, invalid scoring, any real-probe lane triggering execution, Blunder touched, identity regress).

## Hard boundaries (non-negotiable)
No live/market orders, no order/cancel endpoints, no live-submit enablement, no `configs/live_submit.json`/`configs/caps.json` mutation (reuse `CAPS_HASH`/`LIVE_SUBMIT_HASH` from `predator_mesh/v31/probes.py`). No secrets/keys/tokens/raw prompts in any artifact/log/report/dashboard/exception/proof. No browser/PageAgent/Playwright/DOM/browser-research lane. No mined-repo clone/import/execution/blind copy. No live scoring from fixtures/replay/samples/stale-cache/fake-transport/disabled/missing-ack/fuzzy-ack/source-unavailable/ambiguous/not-due/unresolved. No execution bridge from any V36 lane.

## Deliverables summary
- 1 new package (`predator_mesh/v36/`), 1 generator script, 1 backend routes file, 1 main.py edit, 1 test helper + 32 test files.
- All required V36 report artifacts written to `artifacts/dummy/` (full spec list + `final_report_v36.json`, refreshed `final_report.json`/`tests_summary.json`, `dummy_mission_state_report_v22.json`, `dashboard_v36_report_v1.json`).
- Final returned verdict (PASS/PARTIAL/FAIL) with the full status/proof-path summary the spec requires.
