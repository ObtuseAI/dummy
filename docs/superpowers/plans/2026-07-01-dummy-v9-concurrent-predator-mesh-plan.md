# Dummy V9 Concurrent Predator Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Dummy's bounded concurrent autonomous intelligence mesh (scheduler, lanes, recursive data inflow, signal ontology, edge engine, aggression governor, proof ledger, dashboard V9) while preserving V8.2 PASS state and all safety boundaries.

**Architecture:** A thin `predator_mesh/` package exposes dataclasses and a `MeshScheduler` that runs independent async lanes with per-lane/cycle timeouts and concurrency caps. Lanes produce typed results that feed into `EdgeIntelligenceEngine`, `ProofWeightedAggressionGovernor`, and existing `StrategyGovernor` / `LiveBrokerFirewall.submit_rehearsal()`. A `scripts/generate_v9_reports.py` script exercises the mesh and writes redacted artifacts. Dashboard V9 routes expose redacted status. All execution is bounded; live orders remain blocked.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, pytest, pytest-timeout, asyncio, existing Dummy packages (`model_router`, `strategies`, `forecasting`, `live_firewall`, `kalshi`, `dashboard`).

## Global Constraints
- Do not modify canonical Blunder files.
- Do not rename Dummy.
- Do not weaken the Live Broker Firewall.
- Do not place real live orders.
- Do not modify `configs/caps.json`.
- Do not enable `configs/live_submit.json`.
- No model, strategy, adapter, dashboard, forecast, report generator, data-source module, or test may call live order endpoints directly.
- No provider API keys, Kalshi private keys, raw account balances, exact positions, or order instructions in prompts/logs/artifacts/dashboard/exceptions.
- All prompts pass `PromptFirewallV2`; all outputs pass `ModelOutputFirewall`.
- Every external call timeout-bounded: provider calls <=20s, smoke total <=45s, Kalshi read-only <=10s per call.
- No recursive pytest inside unit tests.
- All reports redacted and written to `artifacts/dummy/`.

---

## File Structure

### New package: `predator_mesh/`
- `predator_mesh/__init__.py` — public exports
- `predator_mesh/models.py` — shared mesh dataclasses (`MeshLane`, `MeshTask`, `MeshRun`, `MeshBudget`, `MeshPriority`, `MeshHeartbeat`, `MeshTimeout`, `MeshResult`, `MeshProofRef`, lifecycle/priority enums)
- `predator_mesh/scheduler.py` — `MeshScheduler` with bounded concurrency, timeouts, stuck-task killer
- `predator_mesh/budget.py` — `MeshBudget` tracking provider/Kalshi call counts
- `predator_mesh/proof_ledger.py` — `MeshProofLedger` hook writer
- `predator_mesh/lanes/` package:
  - `__init__.py`
  - `kalshi_terrain.py` — Kalshi READ_ONLY terrain lane
  - `recursive_inflow.py` — recursive data inflow discovery lane
  - `signal_normalization.py` — signal ontology normalization lane
  - `anomaly_mining.py` — edge anomaly detection lane
  - `forecast_update.py` — hybrid forecast update lane
  - `strategy_intelligence.py` — strategy family lane
  - `strategy_governor.py` — strategy governor routing lane
  - `firewall_rehearsal.py` — firewall rehearsal lane
  - `calibration.py` — calibration update lane
  - `mesh_health.py` — mesh health monitoring lane
- `predator_mesh/data_inflow/` package:
  - `__init__.py`
  - `models.py` — `DataSourceCandidate`, `DataSourceScore`, source profiles, promotion/pruning decisions
  - `registry.py` — `DataSourceRegistry`
  - `scoring.py` — `SourceScorer`
  - `adapters.py` — mock/sample adapters for source categories
- `predator_mesh/signals/` package:
  - `__init__.py`
  - `models.py` — `NormalizedSignal`, `SignalType`, signal metadata
  - `normalizer.py` — `SignalNormalizer`
- `predator_mesh/edge/` package:
  - `__init__.py`
  - `models.py` — `EdgeCandidate`, `EdgeScore`, edge decisions
  - `engine.py` — `EdgeIntelligenceEngine`
- `predator_mesh/aggression/` package:
  - `__init__.py`
  - `models.py` — aggression allocation decisions
  - `governor.py` — `ProofWeightedAggressionGovernor`

### New dashboard routes
- `dashboard/backend/v9_routes.py` — V9 API endpoints
- Modify `dashboard/backend/main.py` — mount `/api/v9/...` router

### New report generator
- `scripts/generate_v9_reports.py` — orchestrates mesh run and writes all V9 artifacts

### New tests (`tests/`)
- `test_concurrent_predator_mesh_scheduler.py`
- `test_mesh_lane_registry.py`
- `test_mesh_lane_timeouts.py`
- `test_mesh_stuck_task_killer.py`
- `test_recursive_data_inflow_mesh.py`
- `test_data_source_registry.py`
- `test_data_source_scoring.py`
- `test_source_promotion_pruning.py`
- `test_signal_ontology.py`
- `test_signal_normalization.py`
- `test_edge_intelligence_engine.py`
- `test_edge_candidate_manifest.py`
- `test_edge_decision_report.py`
- `test_mesh_hybrid_model_routing.py`
- `test_mesh_model_failure_degradation.py`
- `test_proof_weighted_aggression_governor.py`
- `test_aggression_allocation_manifest.py`
- `test_mesh_proof_ledger_hooks.py`
- `test_dashboard_v9.py`
- `test_no_secret_leak_v9.py`
- `test_no_llm_secret_leak_v9.py`
- `test_no_live_submit_still_disabled_v9.py`
- `test_direct_order_bypass_v9.py`
- `test_kalshi_read_only_still_passes_v9.py`
- `test_timeout_guards_still_intact_v9.py`
- `test_blunder_separation_v9.py`
- `test_dummy_canonical_identity_v9.py`

---

## Task 1: Scaffold `predator_mesh` package and shared models

**Files:**
- Create: `predator_mesh/__init__.py`
- Create: `predator_mesh/models.py`

**Interfaces:**
- Produces: `MeshLane`, `MeshTask`, `MeshRun`, `MeshBudget`, `MeshPriority`, `MeshHeartbeat`, `MeshTimeout`, `MeshResult`, `MeshProofRef`, `LaneState`, `LanePriority` enums.

- [ ] **Step 1.1:** Create package `__init__.py` exporting `models` symbols.
- [ ] **Step 1.2:** Define Pydantic v2 dataclasses/enums in `models.py` matching the design.
- [ ] **Step 1.3:** Run import check: `python -c "from predator_mesh.models import MeshLane, MeshScheduler; print('ok')"`

Expected output: `ok`

---

## Task 2: Mesh scheduler with bounded concurrency and stuck-task killer

**Files:**
- Create: `predator_mesh/scheduler.py`
- Create: `predator_mesh/budget.py`
- Create: `predator_mesh/proof_ledger.py`

**Interfaces:**
- Consumes: `MeshLane`, `MeshTask`, `MeshRun`, `MeshBudget`, `MeshTimeout`, `MeshResult`, `MeshProofRef` from Task 1.
- Produces: `MeshScheduler.run_cycle(lanes, budget, cycle_timeout)` → `MeshRun`.

- [ ] **Step 2.1:** Implement `MeshBudget` with provider_call_count, kalshi_call_count, max limits.
- [ ] **Step 2.2:** Implement `MeshProofLedger` with `record(event, lane, proof_ref)`.
- [ ] **Step 2.3:** Implement `MeshScheduler`:
  - Priority sorting
  - `asyncio.Semaphore` for max concurrency
  - `asyncio.wait_for` per lane
  - Stuck-task killer via shielded task + cancellation
  - Cycle timeout
  - State transitions: READY→RUNNING→COMPLETED/TIMED_OUT/DEGRADED/QUARANTINED
- [ ] **Step 2.4:** Write `test_concurrent_predator_mesh_scheduler.py` verifying cycle completes and respects max concurrency.
- [ ] **Step 2.5:** Write `test_mesh_lane_timeouts.py` verifying per-lane timeout and cycle timeout.
- [ ] **Step 2.6:** Write `test_mesh_stuck_task_killer.py` verifying non-cancellable blocking task is killed.
- [ ] **Step 2.7:** Run: `pytest tests/test_concurrent_predator_mesh_scheduler.py tests/test_mesh_lane_timeouts.py tests/test_mesh_stuck_task_killer.py -v --timeout=60`

Expected: all pass.

---

## Task 3: Mesh lane registry and lane base classes

**Files:**
- Create: `predator_mesh/lanes/__init__.py`
- Create: `predator_mesh/lanes/base.py`
- Create: `predator_mesh/lane_registry.py`

**Interfaces:**
- Produces: `BaseLane`, `LANE_REGISTRY`, helper `build_default_lanes()`.

- [ ] **Step 3.1:** Define `BaseLane.execute(ctx: MeshContext) -> MeshResult` abstract method.
- [ ] **Step 3.2:** Create registry mapping lane name → class for all 10 lanes.
- [ ] **Step 3.3:** Write `test_mesh_lane_registry.py` verifying registry contains all 10 lanes and builds default list.
- [ ] **Step 3.4:** Run: `pytest tests/test_mesh_lane_registry.py -v --timeout=60`

Expected: pass.

---

## Task 4: Recursive data inflow mesh

**Files:**
- Create: `predator_mesh/data_inflow/models.py`
- Create: `predator_mesh/data_inflow/registry.py`
- Create: `predator_mesh/data_inflow/scoring.py`
- Create: `predator_mesh/data_inflow/adapters.py`
- Create: `predator_mesh/lanes/recursive_inflow.py`

**Interfaces:**
- Produces: `DataSourceCandidate`, `DataSourceRegistry`, `SourceScorer`, `DataSourceScore`, promotion/pruning decisions.

- [ ] **Step 4.1:** Define source category enum and dataclasses.
- [ ] **Step 4.2:** Implement `DataSourceRegistry` with add/update/list/prune methods and mock/sample adapters.
- [ ] **Step 4.3:** Implement `SourceScorer` combining reliability, freshness, latency, uniqueness, edge contribution.
- [ ] **Step 4.4:** Implement `RecursiveDataInflowLane.execute()` returning source candidates.
- [ ] **Step 4.5:** Write `test_recursive_data_inflow_mesh.py`, `test_data_source_registry.py`, `test_data_source_scoring.py`, `test_source_promotion_pruning.py`.
- [ ] **Step 4.6:** Run: `pytest tests/test_recursive_data_inflow_mesh.py tests/test_data_source_registry.py tests/test_data_source_scoring.py tests/test_source_promotion_pruning.py -v --timeout=60`

Expected: all pass.

---

## Task 5: Signal ontology and normalization lane

**Files:**
- Create: `predator_mesh/signals/models.py`
- Create: `predator_mesh/signals/normalizer.py`
- Create: `predator_mesh/lanes/signal_normalization.py`

**Interfaces:**
- Consumes: `DataSourceCandidate` / raw source output.
- Produces: `NormalizedSignal` with `SignalType`, strength, freshness, confidence, source/proof refs.

- [ ] **Step 5.1:** Define `SignalType` enum and `NormalizedSignal` dataclasses.
- [ ] **Step 5.2:** Implement `SignalNormalizer` converting source candidates to signals.
- [ ] **Step 5.3:** Implement `SignalNormalizationLane`.
- [ ] **Step 5.4:** Write `test_signal_ontology.py`, `test_signal_normalization.py`.
- [ ] **Step 5.5:** Run: `pytest tests/test_signal_ontology.py tests/test_signal_normalization.py -v --timeout=60`

Expected: all pass.

---

## Task 6: Edge intelligence engine and anomaly mining lane

**Files:**
- Create: `predator_mesh/edge/models.py`
- Create: `predator_mesh/edge/engine.py`
- Create: `predator_mesh/lanes/anomaly_mining.py`

**Interfaces:**
- Consumes: `NormalizedSignal` list, `MarketTerrainSnapshot`.
- Produces: `EdgeCandidate`, `EdgeDecision`, `EdgeScore`.

- [ ] **Step 6.1:** Define edge scoring dimensions and decision enum.
- [ ] **Step 6.2:** Implement `EdgeIntelligenceEngine.score(signals, terrain) -> list[EdgeCandidate]`.
- [ ] **Step 6.3:** Implement `AnomalyMiningLane`.
- [ ] **Step 6.4:** Write `test_edge_intelligence_engine.py`, `test_edge_candidate_manifest.py`, `test_edge_decision_report.py`.
- [ ] **Step 6.5:** Run: `pytest tests/test_edge_intelligence_engine.py tests/test_edge_candidate_manifest.py tests/test_edge_decision_report.py -v --timeout=60`

Expected: all pass.

---

## Task 7: Remaining mesh lanes

**Files:**
- Create: `predator_mesh/lanes/kalshi_terrain.py`
- Create: `predator_mesh/lanes/forecast_update.py`
- Create: `predator_mesh/lanes/strategy_intelligence.py`
- Create: `predator_mesh/lanes/strategy_governor.py`
- Create: `predator_mesh/lanes/firewall_rehearsal.py`
- Create: `predator_mesh/lanes/calibration.py`
- Create: `predator_mesh/lanes/mesh_health.py`

**Interfaces:**
- Consumes: existing Kalshi READ_ONLY adapters, `HybridForecastEngine`, `StrategyGovernor`, `LiveBrokerFirewall`, calibration tracker.
- Produces: lane-specific results.

- [ ] **Step 7.1:** Implement `KalshiTerrainLane` using existing READ_ONLY path with call budget check.
- [ ] **Step 7.2:** Implement `ForecastUpdateLane` using `HybridForecastEngine.hybrid_review()` with timeout.
- [ ] **Step 7.3:** Implement `StrategyIntelligenceLane` invoking strategy families.
- [ ] **Step 7.4:** Implement `StrategyGovernorLane` routing to `StrategyGovernor.evaluate()`.
- [ ] **Step 7.5:** Implement `FirewallRehearsalLane` calling `LiveBrokerFirewall.submit_rehearsal()` only.
- [ ] **Step 7.6:** Implement `CalibrationLane` tracking forecast/source quality.
- [ ] **Step 7.7:** Implement `MeshHealthLane` detecting stuck/slow/noisy lanes.
- [ ] **Step 7.8:** Run scheduler integration test: `pytest tests/test_concurrent_predator_mesh_scheduler.py -v --timeout=60`

Expected: pass.

---

## Task 8: Hybrid model routing and failure degradation

**Files:**
- Create: `predator_mesh/hybrid_router.py`
- Modify: `predator_mesh/lanes/forecast_update.py` (use hybrid router)

**Interfaces:**
- Consumes: `ModelRouter` from `model_router.router`, `PromptFirewallV2`, `ModelOutputFirewall`.
- Produces: `HybridModelResult` with degraded status on failure.

- [ ] **Step 8.1:** Implement `MeshHybridRouter` that calls DeepSeekV4Flash fast then MinimaxM3 critique concurrently with lane timeout.
- [ ] **Step 8.2:** Add degradation logic: if model fails, return deterministic fallback and mark lane DEGRADED.
- [ ] **Step 8.3:** Write `test_mesh_hybrid_model_routing.py`, `test_mesh_model_failure_degradation.py`.
- [ ] **Step 8.4:** Run: `pytest tests/test_mesh_hybrid_model_routing.py tests/test_mesh_model_failure_degradation.py -v --timeout=60`

Expected: all pass.

---

## Task 9: Proof-weighted aggression governor

**Files:**
- Create: `predator_mesh/aggression/models.py`
- Create: `predator_mesh/aggression/governor.py`

**Interfaces:**
- Consumes: `EdgeCandidate`, source scores, forecast confidence, model agreement/disagreement, calibration support, liquidity/spread, settlement risk, cap impact, no-trade pressure, timeout pressure, source decay, strategy governor output.
- Produces: `AggressionAllocation` decisions.

- [ ] **Step 9.1:** Define `AggressionAllocation` and `AggressionDecision` dataclasses/enums.
- [ ] **Step 9.2:** Implement `ProofWeightedAggressionGovernor.allocate(...)`.
- [ ] **Step 9.3:** Write `test_proof_weighted_aggression_governor.py`, `test_aggression_allocation_manifest.py`.
- [ ] **Step 9.4:** Run: `pytest tests/test_proof_weighted_aggression_governor.py tests/test_aggression_allocation_manifest.py -v --timeout=60`

Expected: all pass.

---

## Task 10: Proof ledger hooks

**Files:**
- Modify: `predator_mesh/proof_ledger.py`
- Modify: all lane files to call `MeshProofLedger.record(...)`

**Interfaces:**
- Produces: `mesh_proof_ledger_report_v1.json` artifact.

- [ ] **Step 10.1:** Add hook calls in each lane for lifecycle events, source promotion/pruning, edge generation/rejection, forecast update, governor decision, firewall rehearsal verdict, model digest, no-secret check, no-order-bypass check.
- [ ] **Step 10.2:** Write `test_mesh_proof_ledger_hooks.py` verifying all expected events are recorded.
- [ ] **Step 10.3:** Run: `pytest tests/test_mesh_proof_ledger_hooks.py -v --timeout=60`

Expected: pass.

---

## Task 11: Dashboard V9 routes

**Files:**
- Create: `dashboard/backend/v9_routes.py`
- Modify: `dashboard/backend/main.py`

**Interfaces:**
- Produces: `/api/v9/mesh/status`, `/api/v9/mesh/lanes`, `/api/v9/data-inflow/sources`, `/api/v9/signals`, `/api/v9/edges`, `/api/v9/aggression-governor`, `/api/v9/mesh-health`, `/api/v9/proof`.

- [ ] **Step 11.1:** Create `v9_routes.py` with redacted JSON responses; no secrets or raw prompts exposed.
- [ ] **Step 11.2:** Mount router in `main.py` under `/api/v9`.
- [ ] **Step 11.3:** Write `test_dashboard_v9.py` using `TestClient`.
- [ ] **Step 11.4:** Run: `pytest tests/test_dashboard_v9.py -v --timeout=60`

Expected: pass.

---

## Task 12: V9 report generator script

**Files:**
- Create: `scripts/generate_v9_reports.py`

**Interfaces:**
- Consumes: all V9 modules.
- Produces: all required V9 artifacts in `artifacts/dummy/`.

- [ ] **Step 12.1:** Implement async `main()` that builds default lanes, runs scheduler, collects reports.
- [ ] **Step 12.2:** Write all required artifacts:
  - `concurrent_predator_mesh_report_v1.json`
  - `mesh_scheduler_report_v1.json`
  - `mesh_timeout_guard_report_v1.json`
  - `mesh_lane_registry_report_v1.json`
  - `mesh_lane_execution_report_v1.json`
  - `recursive_data_inflow_mesh_report_v1.json`
  - `data_source_registry_report_v1.json`
  - `data_source_scoring_report_v1.json`
  - `source_promotion_pruning_report_v1.json`
  - `signal_ontology_report_v1.json`
  - `signal_normalization_report_v1.json`
  - `edge_intelligence_engine_report_v1.json`
  - `edge_candidate_manifest_v1.json`
  - `edge_decision_report_v1.json`
  - `mesh_hybrid_model_routing_report_v1.json`
  - `mesh_model_failure_degradation_report_v1.json`
  - `proof_weighted_aggression_governor_report_v1.json`
  - `aggression_allocation_manifest_v1.json`
  - `mesh_proof_ledger_report_v1.json`
  - `dashboard_v9_report_v1.json`
  - `no_secret_leak_report_v9.json`
  - `no_llm_secret_leak_report_v9.json`
  - `no_live_submit_still_disabled_report_v9.json`
  - `direct_order_bypass_report_v9.json`
  - `blunder_separation_recheck_v9.json`
  - `dummy_canonical_identity_report_v9.json`
  - `final_report_v9.json`
- [ ] **Step 12.3:** Run: `python scripts/generate_v9_reports.py`

Expected: script completes without errors and artifacts are created.

---

## Task 13: Safety and identity tests

**Files:**
- Create: `tests/test_no_secret_leak_v9.py`
- Create: `tests/test_no_llm_secret_leak_v9.py`
- Create: `tests/test_no_live_submit_still_disabled_v9.py`
- Create: `tests/test_direct_order_bypass_v9.py`
- Create: `tests/test_kalshi_read_only_still_passes_v9.py`
- Create: `tests/test_timeout_guards_still_intact_v9.py`
- Create: `tests/test_blunder_separation_v9.py`
- Create: `tests/test_dummy_canonical_identity_v9.py`

- [ ] **Step 13.1:** Implement each test following V8.2 safety test patterns.
- [ ] **Step 13.2:** Run: `pytest tests/test_no_secret_leak_v9.py tests/test_no_llm_secret_leak_v9.py tests/test_no_live_submit_still_disabled_v9.py tests/test_direct_order_bypass_v9.py tests/test_kalshi_read_only_still_passes_v9.py tests/test_timeout_guards_still_intact_v9.py tests/test_blunder_separation_v9.py tests/test_dummy_canonical_identity_v9.py -v --timeout=60`

Expected: all pass.

---

## Task 14: Full regression validation

- [ ] **Step 14.1:** Run: `python -m pytest tests/ -q --tb=short --timeout=60`
  Expected: all pass (target >923 tests).
- [ ] **Step 14.2:** Run: `python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60`
  Expected: pass, capture slowest 25 tests.
- [ ] **Step 14.3:** Run dashboard build: `cd dashboard/frontend && npm run build`
  Expected: build succeeds.
- [ ] **Step 14.4:** Run V8 baseline reports:
  - `python scripts/generate_v8_reports.py`
  - `python scripts/generate_v8_1_reports.py`
  - `python scripts/generate_v8_2_reports.py`
  Expected: all complete.
- [ ] **Step 14.5:** Run V9 report generator: `python scripts/generate_v9_reports.py`
  Expected: all artifacts generated, no secret leakage.

---

## Spec Coverage Self-Review

| Spec Requirement | Task |
|------------------|------|
| Mesh scheduler dataclasses | Task 1 |
| Bounded concurrent lanes | Task 2 |
| 10 mesh lanes | Tasks 3, 7 |
| Recursive data inflow | Task 4 |
| Signal ontology | Task 5 |
| Edge intelligence engine | Task 6 |
| Hybrid model routing | Task 8 |
| Proof-weighted aggression governor | Task 9 |
| Proof ledger hooks | Task 10 |
| Dashboard V9 | Task 11 |
| V9 report generator + artifacts | Task 12 |
| Safety/identity tests | Task 13 |
| Regression validation | Task 14 |

No placeholders. Type names consistent across tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-01-dummy-v9-concurrent-predator-mesh-plan.md`.

**Execution approach:** Subagent-Driven Development — dispatch fresh subagents per task group, review between groups. Given the scope, parallelize independent tasks (data_inflow, signals, edge, aggression can run concurrently after scheduler/models are ready).
