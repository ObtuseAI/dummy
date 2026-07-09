# Dummy V30 In-House Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a small fixture-first in-house adapter set from V29 ADAPTER_SPEC_READY candidates, then prove normalization, settlement compatibility, disabled public-probe readiness, and no execution bridge.

**Architecture:** Add `predator_mesh.v30` with pure Python dataclasses, fixture loader/guards, four adapters, normalization, settlement compatibility, dry-run closure, public probe readiness, sports fixture-only guard, and report generation. Mirror the existing V29 generator/dashboard pattern for artifacts and UI slices.

**Tech Stack:** Python dataclasses and pytest for adapter contracts, JSON report generation, FastAPI read-only report slices, React/Vite dashboard viewer.

---

### Task 1: Red Tests

**Files:**
- Create: `tests/v30_test_helpers.py`
- Create V30 contract tests for adapter selection, base interface, weather, crypto, public-event, Kalshi, fixtures, normalization, settlement, dry-run closure, probe readiness, sports guard, source truth, safety, manifest, and dashboard.

- [ ] **Step 1: Write failing tests**

Tests should import `scripts.generate_v30_reports` and `predator_mesh.v30.adapters`, assert the expected V30 API, and fail while those modules are absent.

- [ ] **Step 2: Run tests for RED**

Run: `python -m pytest tests/test_v30_adapter_implementation_selection_v1.py tests/test_in_house_adapter_base_interface_v1.py tests/test_weather_public_observation_adapter_v1.py tests/test_crypto_public_price_adapter_v1.py tests/test_public_event_reference_adapter_v1.py tests/test_kalshi_readonly_rule_adapter_v1.py tests/test_adapter_fixture_contract_implementation_v1.py tests/test_adapter_normalization_pipeline_v1.py tests/test_adapter_to_settlement_compatibility_v1.py tests/test_adapter_observation_closure_dry_run_v1.py tests/test_public_probe_implementation_readiness_v3.py tests/test_sports_fixture_only_adapter_guard_v1.py tests/test_adapter_source_truth_v11.py tests/test_adapter_implementation_partial_reduction_v1.py tests/test_v30_required_report_manifest.py tests/test_no_adapter_implementation_to_execution_bridge_v30.py tests/test_dashboard_v30.py -q --tb=short`

Expected: FAIL because V30 modules and reports do not exist.

### Task 2: Adapter Implementation

**Files:**
- Create: `predator_mesh/v30/__init__.py`
- Create: `predator_mesh/v30/adapters.py`
- Create: `predator_mesh/v30/reports.py`
- Create: `scripts/generate_v30_reports.py`

- [ ] **Step 1: Implement base interface**

Add `AdapterRequestV1`, `AdapterResponseV1`, `AdapterEvidencePacketV1`, `AdapterSourceRefV1`, `AdapterErrorV1`, `AdapterRuntimeGuardV1`, and `InHouseAdapterBaseInterfaceV1`.

- [ ] **Step 2: Implement selected adapters**

Implement fixture-first weather observation, crypto public price, public event/reference, and Kalshi READ_ONLY rule adapters. Defer sports, trading, and Bloomberg specs with explicit blockers.

- [ ] **Step 3: Implement fixture, normalization, settlement, dry-run, readiness, source-truth helpers**

Keep all fixture/sample evidence non-live and non-scoreable unless explicit future `LIVE_PUBLIC_PROBE_RESULT` evidence exists.

- [ ] **Step 4: Generate all V30 reports**

Produce required reports, `final_report_v30.json`, update `final_report.json`, and update `tests_summary.json`.

### Task 3: Dashboard

**Files:**
- Create: `dashboard/backend/v30_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V30Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] **Step 1: Add V30 API slices**

Expose mission, adapters, fixtures, normalization, settlement, dry-run, probe-readiness, sports, source-truth, and safety report slices.

- [ ] **Step 2: Add V30 dashboard viewer**

Mirror the V29 artifact viewer and summarize implemented adapter count, normalized packets, settlement-compatible packets, dry-run score eligibility, integration mode, and safety.

### Task 4: Verification

- [ ] **Step 1:** `python scripts/generate_v30_reports.py`
- [ ] **Step 2:** targeted V30 pytest suite
- [ ] **Step 3:** `python -m py_compile predator_mesh/v30/__init__.py predator_mesh/v30/adapters.py predator_mesh/v30/reports.py scripts/generate_v30_reports.py dashboard/backend/v30_routes.py`
- [ ] **Step 4:** `cd dashboard/frontend && npm run build`
- [ ] **Step 5:** full pytest regression with durations
- [ ] **Step 6:** protected config hashes and banned-fragment safety scan
