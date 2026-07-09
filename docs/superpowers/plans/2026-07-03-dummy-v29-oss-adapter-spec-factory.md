# Dummy V29 OSS Adapter Spec Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the expanded V28 metadata-only OSS candidate universe into deterministic V29 triage, adapter-spec, fixture, public-probe-readiness, and safety reports without cloning, importing, executing, or copying mined repo code.

**Architecture:** Follow the existing V28 report-factory pattern. A pure Python `predator_mesh.v29.reports` module reads the current raw OSS metadata artifact, normalizes and scores candidates, emits report payloads, and is called by `scripts/generate_v29_reports.py`; tests assert contracts through `tests/v29_test_helpers.py`, and dashboard slices expose artifact-backed summaries.

**Tech Stack:** Python JSON report generation, pytest contract tests, FastAPI route slices, React/Vite dashboard viewer.

---

### Task 1: Requirement Extraction And Red Tests

**Files:**
- Create: `tests/v29_test_helpers.py`
- Create: `tests/test_oss_candidate_universe_normalizer_v1.py`
- Create: `tests/test_adapter_spec_factory_v1.py`
- Create: `tests/test_public_probe_readiness_planner_v2.py`
- Create: `tests/test_no_browser_automation_v29.py`
- Create: `tests/test_no_mined_repo_execution_v29.py`
- Create: `tests/test_dashboard_v29.py`

- [ ] **Step 1: Write failing helper/test contracts**

```python
from tests.v29_test_helpers import assert_v29_report_named

def test_oss_candidate_universe_normalizer_v1_preserves_current_v28_expansion() -> None:
    report = assert_v29_report_named(
        "oss_candidate_universe_normalizer_v1_report.json",
        "canonical_candidate_count",
        "category_counts",
        "keyword_provenance_status",
    )
    assert report["raw_candidate_count"] >= 246
    assert report["canonical_candidate_count"] >= 246
```

- [ ] **Step 2: Run the new tests to verify RED**

Run: `python -m pytest tests/test_oss_candidate_universe_normalizer_v1.py tests/test_adapter_spec_factory_v1.py tests/test_public_probe_readiness_planner_v2.py tests/test_no_browser_automation_v29.py tests/test_no_mined_repo_execution_v29.py tests/test_dashboard_v29.py -q --tb=short`

Expected: FAIL because `scripts.generate_v29_reports` and dashboard routes do not exist.

### Task 2: V29 Report Factory And Generator

**Files:**
- Create: `predator_mesh/v29/__init__.py`
- Create: `predator_mesh/v29/reports.py`
- Create: `scripts/generate_v29_reports.py`
- Create: `artifacts/dummy/v29_required_report_names_from_attachment.txt`

- [ ] **Step 1: Implement pure metadata-only candidate loading**

Read `artifacts/dummy/github_gap_fill_candidates_raw_v1.json`, preserve raw metadata, produce stable canonical IDs, category counts, keyword provenance, and duplicate clusters. Do not network, clone, import, or execute candidate repositories.

- [ ] **Step 2: Implement triage/scoring/spec payloads**

Generate license/terms verdicts, maintenance scores, market-class fit records, in-house adapter specs, fixture schemas, contract-test plans, public-probe-readiness plans, settlement-gap mapping, domain packs, promotion gate counts, sprint queue, compounding recommendation, scoreboard, mission-state report, and safety reports.

- [ ] **Step 3: Implement generator indexes**

Write all report JSON files plus `final_report_v29.json`, update `final_report.json` with a V29 snapshot, and append V29 report/test metadata into `tests_summary.json`.

### Task 3: Dashboard Slices

**Files:**
- Create: `dashboard/backend/v29_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V29Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] **Step 1: Add FastAPI route slices**

Expose `/api/v29/mission-state`, `/api/v29/oss-candidates`, `/api/v29/triage`, `/api/v29/adapter-specs`, `/api/v29/probe-readiness`, `/api/v29/domain-packs`, and `/api/v29/safety` from generated report payloads.

- [ ] **Step 2: Add React V29 dashboard route**

Mirror the V28 viewer with V29 summary cards for verdict, total candidates, adapter specs, fixture contracts, public probe readiness, sports mode, integration mode, and safety.

### Task 4: Verification

**Files:**
- Generated artifacts under `artifacts/dummy/*.json`

- [ ] **Step 1: Generate V29 artifacts**

Run: `python scripts/generate_v29_reports.py`

- [ ] **Step 2: Run targeted V29 tests**

Run: `python -m pytest tests/test_oss_candidate_universe_normalizer_v1.py tests/test_adapter_spec_factory_v1.py tests/test_public_probe_readiness_planner_v2.py tests/test_no_browser_automation_v29.py tests/test_no_mined_repo_execution_v29.py tests/test_dashboard_v29.py -q --tb=short`

- [ ] **Step 3: Run broader contract and build checks**

Run: `python -m pytest tests/ -q --tb=short --timeout=60 --durations=25`

Run: `cd dashboard/frontend && npm run build`

- [ ] **Step 4: Verify safety invariants**

Check `configs/live_submit.json` and `configs/caps.json` hashes, scan V29 reports for banned secret/order/browser/mined-code fragments, and report final PASS/PARTIAL/FAIL with proof paths.
