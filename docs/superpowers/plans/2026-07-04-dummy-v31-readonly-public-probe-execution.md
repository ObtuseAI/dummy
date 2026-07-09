# Dummy V31 Readonly Public Probe Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `DUMMY_V31_EXPLICIT_READONLY_PUBLIC_PROBE_EXECUTION_OBSERVATION_CLOSURE_AND_LIVE_SCORE_SEED_V1` as a disabled-by-default, read-only bridge from V30 adapters to bounded public probe evidence, observation closure, and live score seeds.

**Architecture:** Add a focused `predator_mesh.v31` package that depends on V30 adapter contracts but never imports execution, order, cancel, browser, or mined-repo code. Use injectable public probe transports so unit tests prove enabled behavior without live network, while the default operator gate remains disabled. Generate deterministic V31 artifacts from a report factory and expose dashboard slices through `/api/v31/*`.

**Tech Stack:** Python dataclasses, pytest, FastAPI routes, React/Vite dashboard, existing `artifacts/dummy` report convention.

---

### Task 1: Gate, Probe Runner, Evidence, Closure, And Score Tests

**Files:**
- Create: `tests/v31_test_helpers.py`
- Create: `tests/test_explicit_public_probe_operator_gate_v3.py`
- Create: `tests/test_v30_adapter_public_probe_runner_v1.py`
- Create: `tests/test_live_public_evidence_capture_v1.py`
- Create: `tests/test_probe_evidence_normalization_pipeline_v2.py`
- Create: `tests/test_due_forecast_live_observation_closure_v4.py`
- Create: `tests/test_live_score_seed_v2.py`

- [ ] **Step 1: Write failing tests for the default disabled gate**

```python
from predator_mesh.v31.probes import ExplicitPublicProbeOperatorGateV3


def test_public_probe_gate_is_disabled_by_default_and_preserves_config_hashes() -> None:
    decision = ExplicitPublicProbeOperatorGateV3().decide({})

    assert decision.enabled is False
    assert decision.state == "DISABLED_BY_DEFAULT"
    assert decision.reason == "EXPLICIT_OPERATOR_GATE_NOT_SET"
    assert decision.max_requests == 0
    assert decision.safety_proof.no_execution_bridge is True
    assert decision.config_diff_proof.live_submit_modified is False
    assert decision.config_diff_proof.caps_modified is False
```

- [ ] **Step 2: Run the gate test to verify RED**

Run: `python -m pytest tests/test_explicit_public_probe_operator_gate_v3.py -q --tb=short`

Expected: import failure for `predator_mesh.v31`.

- [ ] **Step 3: Write failing tests for enabled fake-transport probe runs**

```python
from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    V30AdapterPublicProbeRunnerV1,
)


def test_probe_runner_executes_only_bounded_readonly_tasks_when_gate_enabled() -> None:
    env = {
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    }
    gate = ExplicitPublicProbeOperatorGateV3().decide(env)
    runner = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1())

    result = runner.run(gate)

    assert gate.enabled is True
    assert result.probe_run_count == 3
    assert result.source_family_count >= 3
    assert result.execution_bridge_present is False
    assert all(item.read_only is True for item in result.results)
    assert all(item.source_api_key_required is False for item in result.results)
    assert all(item.order_endpoint_used is False for item in result.results)
```

- [ ] **Step 4: Run runner tests to verify RED**

Run: `python -m pytest tests/test_v30_adapter_public_probe_runner_v1.py -q --tb=short`

Expected: import failure for `predator_mesh.v31`.

- [ ] **Step 5: Write failing tests for evidence capture and normalization mode separation**

```python
from predator_mesh.v30.adapters import build_default_v30_context
from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)


def test_live_public_evidence_capture_accepts_only_enabled_probe_results() -> None:
    disabled = ExplicitPublicProbeOperatorGateV3().decide({})
    disabled_run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(disabled)
    disabled_packets = LivePublicEvidenceCaptureV1().capture(disabled_run)
    assert disabled_packets == []

    enabled = ExplicitPublicProbeOperatorGateV3().decide({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(enabled)
    packets = LivePublicEvidenceCaptureV1().capture(run)

    assert len(packets) == 3
    assert all(packet.mode == "LIVE_PUBLIC_PROBE_RESULT" for packet in packets)
    assert all(packet.live_observation_eligible is True for packet in packets)
    assert all(packet.execution_bridge_present is False for packet in packets)


def test_probe_normalization_rejects_v30_fixtures_as_live_public_evidence() -> None:
    fixture_packets = build_default_v30_context()["packets"]
    normalized = ProbeEvidenceNormalizationPipelineV2().normalize_fixture_packets(fixture_packets)

    assert all(item.live_observation_eligible is False for item in normalized)
    assert all(item.live_score_eligible is False for item in normalized)
    assert {item.mode for item in normalized} >= {"REPLAY_FIXTURE_RESPONSE", "PUBLIC_SAMPLE_RESPONSE", "CACHED_PUBLIC_PROBE_RESULT"}
```

- [ ] **Step 6: Run evidence tests to verify RED**

Run: `python -m pytest tests/test_live_public_evidence_capture_v1.py tests/test_probe_evidence_normalization_pipeline_v2.py -q --tb=short`

Expected: import failure for `predator_mesh.v31`.

- [ ] **Step 7: Write failing tests for due closure and live score safety**

```python
from predator_mesh.v31.probes import (
    DueForecastLiveObservationClosureV4,
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    LiveScoreSeedV2,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)


def test_due_forecast_closure_observes_only_due_matching_live_public_evidence() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    live_packets = LivePublicEvidenceCaptureV1().capture(run)
    normalized = ProbeEvidenceNormalizationPipelineV2().normalize_live_packets(live_packets)

    closure = DueForecastLiveObservationClosureV4().close(normalized)

    assert closure.due_forecast_count == 4
    assert closure.observed_forecast_count == 3
    assert closure.live_unresolved_count == 1
    assert "SETTLEMENT_AMBIGUOUS" in closure.blockers
    assert closure.outcome_fabricated is False


def test_live_score_seed_scores_only_observed_live_public_outcomes() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    packets = ProbeEvidenceNormalizationPipelineV2().normalize_live_packets(LivePublicEvidenceCaptureV1().capture(run))
    closure = DueForecastLiveObservationClosureV4().close(packets)

    seed = LiveScoreSeedV2().seed(closure)

    assert seed.live_scored_count == 3
    assert seed.fixture_scored_live is False
    assert seed.public_sample_scored_live is False
    assert seed.ambiguous_settlement_scored is False
    assert seed.execution_bridge_present is False
```

- [ ] **Step 8: Run closure and scoring tests to verify RED**

Run: `python -m pytest tests/test_due_forecast_live_observation_closure_v4.py tests/test_live_score_seed_v2.py -q --tb=short`

Expected: import failure for `predator_mesh.v31`.

### Task 2: Report, Dashboard, And Safety Tests

**Files:**
- Create: `tests/test_v31_required_report_manifest.py`
- Create: `tests/test_dashboard_v31.py`
- Create: `tests/test_no_public_probe_gate_to_execution_bridge_v31.py`
- Create: `tests/test_no_public_probe_failure_scored_live_v31.py`
- Create: `tests/test_public_probe_cache_and_audit_v1.py`
- Create: `tests/test_probe_source_truth_v12.py`

- [ ] **Step 1: Write failing tests for required V31 artifacts**

```python
from scripts.generate_v31_reports import generate_all_v31_reports_for_tests


def test_v31_required_report_manifest_contains_core_reports() -> None:
    reports = generate_all_v31_reports_for_tests(enable_network=False)
    final = reports["final_report_v31.json"]

    assert final["required_report_count"] >= 130
    assert final["all_required_reports_generated"] is True
    assert final["public_probe_gate_state"] == "DISABLED_BY_DEFAULT"
    assert final["probe_run_count"] == 0
    assert final["live_scored_count"] == 0
```

- [ ] **Step 2: Run report test to verify RED**

Run: `python -m pytest tests/test_v31_required_report_manifest.py -q --tb=short`

Expected: import failure for `scripts.generate_v31_reports`.

- [ ] **Step 3: Write failing tests for dashboard slices and safety reports**

```python
from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v31_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    for endpoint in [
        "/api/v31/mission-state",
        "/api/v31/gate",
        "/api/v31/probe-runner",
        "/api/v31/evidence",
        "/api/v31/closure",
        "/api/v31/scoring",
        "/api/v31/cache-audit",
        "/api/v31/source-truth",
        "/api/v31/safety",
    ]:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "github_pat_" not in response.text
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
```

- [ ] **Step 4: Run dashboard test to verify RED**

Run: `python -m pytest tests/test_dashboard_v31.py -q --tb=short`

Expected: 404 or missing router/import.

### Task 3: Implement V31 Core Probe Package

**Files:**
- Create: `predator_mesh/v31/__init__.py`
- Create: `predator_mesh/v31/probes.py`

- [ ] **Step 1: Implement gate dataclasses and disabled-by-default decision**
- [ ] **Step 2: Implement fake and HTTP JSON read-only transports**
- [ ] **Step 3: Implement bounded probe plan/tasks/results for weather, crypto, public event, and Kalshi READ_ONLY**
- [ ] **Step 4: Implement evidence capture, normalization, due forecast closure, live score seed, calibration seed, cache writer, audit ledger, sports guard, and source truth helpers**
- [ ] **Step 5: Run V31 core tests until green**

Run: `python -m pytest tests/test_explicit_public_probe_operator_gate_v3.py tests/test_v30_adapter_public_probe_runner_v1.py tests/test_live_public_evidence_capture_v1.py tests/test_probe_evidence_normalization_pipeline_v2.py tests/test_due_forecast_live_observation_closure_v4.py tests/test_live_score_seed_v2.py -q --tb=short`

Expected: all pass, no live network required.

### Task 4: Implement V31 Reports And Generator

**Files:**
- Create: `predator_mesh/v31/reports.py`
- Create: `scripts/generate_v31_reports.py`

- [ ] **Step 1: Implement required report name list from the V31 attachment**
- [ ] **Step 2: Implement report state for disabled default and optional fake enabled mode**
- [ ] **Step 3: Implement mission-state V17 and final-report V31 passthrough keys**
- [ ] **Step 4: Write `artifacts/dummy/v31_required_report_names_from_attachment.txt`, all required reports, `final_report_v31.json`, `final_report.json`, and `tests_summary.json`**
- [ ] **Step 5: Run report tests until green**

Run: `python -m pytest tests/test_v31_required_report_manifest.py tests/test_public_probe_cache_and_audit_v1.py tests/test_probe_source_truth_v12.py tests/test_no_public_probe_gate_to_execution_bridge_v31.py tests/test_no_public_probe_failure_scored_live_v31.py -q --tb=short`

Expected: all pass.

### Task 5: Implement Dashboard Wiring

**Files:**
- Create: `dashboard/backend/v31_routes.py`
- Modify: `dashboard/backend/main.py`
- Create: `dashboard/frontend/src/V31Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx`

- [ ] **Step 1: Add `/api/v31/*` report slices**
- [ ] **Step 2: Include V31 router in FastAPI app**
- [ ] **Step 3: Add V31 dashboard view and navigation route**
- [ ] **Step 4: Run dashboard tests and build**

Run: `python -m pytest tests/test_dashboard_v31.py -q --tb=short`

Run: `cd dashboard/frontend && npm run build`

Expected: tests pass and Vite build succeeds.

### Task 6: Verification And Final Proof

**Files:**
- Generated: `artifacts/dummy/*v31*.json`
- Generated: `artifacts/dummy/final_report_v31.json`

- [ ] **Step 1: Compile Python V31 files**

Run: `python -m py_compile predator_mesh/v31/__init__.py predator_mesh/v31/probes.py predator_mesh/v31/reports.py scripts/generate_v31_reports.py dashboard/backend/v31_routes.py`

- [ ] **Step 2: Generate V31 reports**

Run: `python scripts/generate_v31_reports.py`

- [ ] **Step 3: Run targeted V31 suite**

Run: `python -m pytest tests/test_explicit_public_probe_operator_gate_v3.py tests/test_v30_adapter_public_probe_runner_v1.py tests/test_live_public_evidence_capture_v1.py tests/test_probe_evidence_normalization_pipeline_v2.py tests/test_due_forecast_live_observation_closure_v4.py tests/test_live_score_seed_v2.py tests/test_v31_required_report_manifest.py tests/test_public_probe_cache_and_audit_v1.py tests/test_probe_source_truth_v12.py tests/test_no_public_probe_gate_to_execution_bridge_v31.py tests/test_no_public_probe_failure_scored_live_v31.py tests/test_dashboard_v31.py -q --tb=short`

- [ ] **Step 4: Run dashboard build**

Run: `cd dashboard/frontend && npm run build`

- [ ] **Step 5: Verify protected config hashes**

Run: `Get-FileHash -Algorithm SHA256 configs/live_submit.json, configs/caps.json`

Expected live-submit hash: `BE5AEDC7D6FAF5B5FA252A0AD06AF240BD04F6E4A5CF17647EC4BBC92C9ABBC9`

Expected caps hash: `F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5`

- [ ] **Step 6: Run V31 safety scan**

Run: `rg -n "playwright|browser_use|PageAgent|selenium|submit_order\\(|cancel_order\\(|private_key\\s*=|api_key\\s*=|github_pat_" predator_mesh/v31 scripts/generate_v31_reports.py dashboard/backend/v31_routes.py dashboard/frontend/src/V31Dashboard.jsx`

Expected: no suspicious runtime hits.

- [ ] **Step 7: Run full regression**

Run: `python -m pytest tests/ -q --tb=short --timeout=60 --durations=25`

Expected: full suite passes with existing skips/warnings only.
