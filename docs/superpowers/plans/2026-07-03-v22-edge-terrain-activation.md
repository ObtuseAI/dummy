# V22 Edge Terrain Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Dummy V22 edge-role activation, forecast-write breakthrough, source-acquisition control, dashboard endpoints, reports, and invariant tests while keeping execution locked.

**Architecture:** Follow the existing V21 pattern: deterministic report objects in a new `predator_mesh.v22` package, a `scripts/generate_v22_reports.py` bundle writer, thin FastAPI routes under `/api/v22`, and helper-driven tests. Unit tests use fixture/static deterministic paths; real source probing remains bounded to generator/integration paths and disabled in tests.

**Tech Stack:** Python dataclasses/report dictionaries, pytest, FastAPI, React/Vite dashboard.

---

### Task 1: V22 Contract Tests

**Files:**
- Create: `tests/v22_test_helpers.py`
- Create V22 tests listed in the user request under `tests/`

- [ ] Write helper tests first so `predator_mesh.v22` and `scripts.generate_v22_reports` are required by tests.
- [ ] Run a representative V22 test and verify it fails with missing module/report names.

### Task 2: V22 Report Domain Model

**Files:**
- Create: `predator_mesh/v22/__init__.py`
- Create: `predator_mesh/v22/reports.py`

- [ ] Implement normalized evidence packets for NWS, SEC, World Bank, Coinbase, and Kraken.
- [ ] Implement role classification, edge activation, context guards, market/event mapping, Kalshi read-only mapping, forecast/no-trade writes, observer queue, V17 ledger integration, acquisition queues, GitHub adapter queue, compounding, scoreboard, mission state, runtime budget, and invariant reports.
- [ ] Keep all live execution flags false, all source/key values redacted, fixtures blocked from real/edge promotion, and context-only evidence blocked from edge claims.

### Task 3: V22 Generator

**Files:**
- Create: `scripts/generate_v22_reports.py`

- [ ] Generate all required V22 reports plus `final_report_v22.json`.
- [ ] Update `final_report.json` and `tests_summary.json` with V22 entries.
- [ ] Keep network disabled for test bundle generation and bounded when explicitly enabled.

### Task 4: Dashboard V22

**Files:**
- Create: `dashboard/backend/v22_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V22Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] Add the required `/api/v22/*` routes.
- [ ] Add the dashboard view that fetches all V22 route groups and displays summary/report payloads without secrets.
- [ ] Build the frontend.

### Task 5: Verification

**Files:**
- Generated: `artifacts/dummy/*.json`

- [ ] Run representative V22 tests after implementation.
- [ ] Run the requested full pytest commands, dashboard build, V8-through-V22 generators, and capture counts/slowest tests.
- [ ] Recheck protected config status for `configs/caps.json` and `configs/live_submit.json`.
