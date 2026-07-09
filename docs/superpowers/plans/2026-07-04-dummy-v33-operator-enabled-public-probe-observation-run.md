# Dummy V33 Operator Enabled Public Probe Observation Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `DUMMY_V33_OPERATOR_ENABLED_PUBLIC_PROBE_OBSERVATION_RUN_V1` as a safe, default-disabled, exact-operator-gated public probe observation run over the V31/V32 probe and closure spine.

**Architecture:** Add a focused `predator_mesh.v33` package that composes V31 fake/adapter probe primitives with V32 closure concepts under a hardened exact acknowledgement gate. Default state remains `DISABLED_BY_DEFAULT` with zero probes/evidence/scores; explicitly enabled test state uses bounded fake transport and never touches live trading, browser automation, secrets, mined repositories, caps, or live-submit.

**Tech Stack:** Python dataclasses, pytest, deterministic JSON report generation, FastAPI routes, React/Vite dashboard.

---

### Task 1: Red Tests For V33 Core

**Files:**
- Create: `tests/v33_test_helpers.py`
- Create: `tests/test_v33_operator_enabled_probe_run_controller_v1.py`
- Create: `tests/test_exact_gate_acknowledgement_hardening_v3.py`
- Create: `tests/test_minimal_live_public_probe_execution_v1.py`
- Create: `tests/test_live_public_evidence_ingestion_v3.py`
- Create: `tests/test_settlement_evidence_join_v3.py`
- Create: `tests/test_due_forecast_observation_run_v6.py`
- Create: `tests/test_live_score_observation_run_v4.py`

- [ ] **Step 1: Write tests proving missing mode/ack fails closed with exact operator action.**
- [ ] **Step 2: Write tests proving fuzzy, misspelled, and live-trading acknowledgements fail closed.**
- [ ] **Step 3: Write tests proving exact enabled fake-transport run creates bounded probe outcomes, evidence packets, joins, closures, scores, and low-sample calibration warning.**
- [ ] **Step 4: Run the V33 core tests and confirm RED import failures for `predator_mesh.v33`.**

### Task 2: Red Tests For Reports, Dashboard, And Safety

**Files:**
- Create: `tests/test_v33_required_report_manifest.py`
- Create: `tests/test_public_probe_artifact_cache_v3.py`
- Create: `tests/test_enabled_probe_audit_ledger_v2.py`
- Create: `tests/test_sports_probe_exclusion_guard_v4.py`
- Create: `tests/test_source_truth_enabled_probe_evidence_v14.py`
- Create: `tests/test_no_missing_ack_probe_run_v33.py`
- Create: `tests/test_no_fuzzy_ack_probe_run_v33.py`
- Create: `tests/test_no_operator_enabled_probe_run_to_execution_bridge_v33.py`
- Create: `tests/test_dashboard_v33.py`

- [ ] **Step 1: Write tests for V33 final report rollup and attachment-required report count.**
- [ ] **Step 2: Write tests for cache/audit/sports/source-truth report contracts.**
- [ ] **Step 3: Write tests for missing/fuzzy ack safety reports and no execution bridge reports.**
- [ ] **Step 4: Write tests for `/api/v33/*` dashboard slices.**
- [ ] **Step 5: Run the report/dashboard tests and confirm RED on missing generator and routes.**

### Task 3: Implement V33 Core Package

**Files:**
- Create: `predator_mesh/v33/__init__.py`
- Create: `predator_mesh/v33/run.py`

- [ ] **Step 1: Implement exact acknowledgement hardening with safe metadata only.**
- [ ] **Step 2: Implement operator-enabled probe run controller and disabled operator packet.**
- [ ] **Step 3: Implement minimal live public probe execution using V31 fake transport for deterministic enabled tests.**
- [ ] **Step 4: Implement weather, crypto, public-event, and Kalshi READ_ONLY enabled domain summaries.**
- [ ] **Step 5: Implement evidence ingestion, settlement join, observation run, score run, calibration, cache, audit, sports exclusion, source truth, partial reduction, queues, and scoreboard.**
- [ ] **Step 6: Run V33 core tests until green.**

### Task 4: Implement Reports And Generator

**Files:**
- Create: `predator_mesh/v33/reports.py`
- Create: `scripts/generate_v33_reports.py`

- [ ] **Step 1: Add the attachment-required V33 report manifest.**
- [ ] **Step 2: Implement deterministic disabled-default report state and enabled fake-run hooks for tests.**
- [ ] **Step 3: Generate all required reports, `final_report_v33.json`, compact shared `final_report.json`, and `tests_summary.json`.**
- [ ] **Step 4: Run report and safety tests until green.**

### Task 5: Implement Dashboard

**Files:**
- Create: `dashboard/backend/v33_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V33Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] **Step 1: Add the 21 `/api/v33/*` report slices from the attachment.**
- [ ] **Step 2: Include the V33 router in the FastAPI app.**
- [ ] **Step 3: Add V33 dashboard view and navigation route.**
- [ ] **Step 4: Run dashboard tests and Vite build.**

### Task 6: Verification

**Files:**
- Generated: `artifacts/dummy/*v33*.json`
- Generated: `artifacts/dummy/final_report_v33.json`

- [ ] **Step 1: Compile V33 Python files.**
- [ ] **Step 2: Generate V33 reports and inspect final summary.**
- [ ] **Step 3: Run targeted V33 test suite.**
- [ ] **Step 4: Run dashboard build.**
- [ ] **Step 5: Verify protected hashes for `configs/live_submit.json` and `configs/caps.json`.**
- [ ] **Step 6: Run V33 source safety scan for browser/order/secret fragments.**
- [ ] **Step 7: Run full regression with slowest 25 durations.**
- [ ] **Step 8: Regenerate V33 reports after full regression so shared final index points to V33.**
