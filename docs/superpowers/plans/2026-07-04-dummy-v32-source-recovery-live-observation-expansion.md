# Dummy V32 Source Recovery Live Observation Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `DUMMY_V32_SOURCE_RECOVERY_LIVE_OBSERVATION_EXPANSION_V1` as a source-recovery and closure expansion around the existing V31 explicit read-only probe gate.

**Architecture:** Add a focused `predator_mesh.v32` package that composes V31 gate, runner, fake transport, evidence, closure, and score seed contracts. Default mode remains disabled and deterministic; enabled-path behavior is covered with injected fake transport so tests never need live network. Generate V32 artifacts in `artifacts/dummy`, keep shared `final_report.json` compact, and expose `/api/v32/*` dashboard slices.

**Tech Stack:** Python dataclasses, pytest, FastAPI routes, React/Vite dashboard, existing `artifacts/dummy` report convention.

---

### Task 1: Red Tests For V32 Core

**Files:**
- Create: `tests/v32_test_helpers.py`
- Create: `tests/test_v32_source_recovery_controller_v1.py`
- Create: `tests/test_operator_gated_probe_run_v2.py`
- Create: `tests/test_minimal_public_probe_pass_v1.py`
- Create: `tests/test_live_public_evidence_expansion_v2.py`
- Create: `tests/test_settlement_compatible_evidence_expansion_v2.py`
- Create: `tests/test_due_forecast_closure_expansion_v5.py`
- Create: `tests/test_live_score_expansion_seed_v3.py`

- [ ] **Step 1: Write tests for disabled source recovery and exact operator action.**
- [ ] **Step 2: Write tests for exact ack validation and enabled fake-transport probe path.**
- [ ] **Step 3: Write tests for evidence, settlement-compatible joins, closure, score, and calibration expansion.**
- [ ] **Step 4: Run targeted V32 tests and confirm RED import failures for `predator_mesh.v32`.**

### Task 2: Red Tests For Reports, Dashboard, And Safety

**Files:**
- Create: `tests/test_v32_required_report_manifest.py`
- Create: `tests/test_probe_cache_replay_separation_v2.py`
- Create: `tests/test_source_truth_recovery_closure_v13.py`
- Create: `tests/test_no_source_recovery_to_execution_bridge_v32.py`
- Create: `tests/test_no_disabled_probe_scored_live_v32.py`
- Create: `tests/test_dashboard_v32.py`

- [ ] **Step 1: Write tests for V32 final report and required artifacts.**
- [ ] **Step 2: Write tests for cache/replay separation, source truth V13, and no execution bridges.**
- [ ] **Step 3: Write tests for `/api/v32/*` dashboard slices.**
- [ ] **Step 4: Run tests and confirm RED on missing report generator/dashboard route.**

### Task 3: Implement V32 Core Package

**Files:**
- Create: `predator_mesh/v32/__init__.py`
- Create: `predator_mesh/v32/recovery.py`

- [ ] **Step 1: Implement source recovery cases/plans/decisions from V31 unresolved states.**
- [ ] **Step 2: Implement operator-gated probe run V2 with exact ack validation.**
- [ ] **Step 3: Implement minimal public probe pass using V31 fake/HTTP transport injection.**
- [ ] **Step 4: Implement domain recovery summaries for weather, crypto, public event, and Kalshi READ_ONLY.**
- [ ] **Step 5: Implement live evidence expansion, settlement-compatible evidence, due closure V5, live score V3, calibration V3, cache separation, sports guard, source truth V13, and default state builder.**
- [ ] **Step 6: Run core V32 tests until green.**

### Task 4: Implement Reports And Generator

**Files:**
- Create: `predator_mesh/v32/reports.py`
- Create: `scripts/generate_v32_reports.py`

- [ ] **Step 1: Implement V32 required report list from the attachment.**
- [ ] **Step 2: Implement deterministic default-disabled V32 report state and enabled fake-run test hooks.**
- [ ] **Step 3: Generate all required reports, `final_report_v32.json`, compact shared `final_report.json`, and `tests_summary.json`.**
- [ ] **Step 4: Run report and safety tests until green.**

### Task 5: Implement Dashboard

**Files:**
- Create: `dashboard/backend/v32_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V32Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] **Step 1: Add `/api/v32/*` report slices.**
- [ ] **Step 2: Include V32 router in FastAPI app.**
- [ ] **Step 3: Add V32 dashboard view and navigation route.**
- [ ] **Step 4: Run dashboard tests and Vite build.**

### Task 6: Verification

**Files:**
- Generated: `artifacts/dummy/*v32*.json`
- Generated: `artifacts/dummy/final_report_v32.json`

- [ ] **Step 1: Compile V32 Python files.**
- [ ] **Step 2: Generate V32 reports and inspect final summary.**
- [ ] **Step 3: Run targeted V32 test suite.**
- [ ] **Step 4: Run dashboard build.**
- [ ] **Step 5: Verify protected hashes for `configs/live_submit.json` and `configs/caps.json`.**
- [ ] **Step 6: Run V32 source safety scan for browser/order/secret fragments.**
- [ ] **Step 7: Run full regression with durations.**
