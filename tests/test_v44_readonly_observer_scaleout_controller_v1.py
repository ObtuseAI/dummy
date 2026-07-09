from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v44_test_helpers import ObserverScaleoutReadOnlyTransport, v44_reports


def test_v44_controller_default_blocks_without_gate() -> None:
    reports = v44_reports()
    report = reports["v44_readonly_observer_scaleout_controller_v1_report.json"]
    assert report["observer_scaleout_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v43_cumulative_real_scored_count"] >= 27
    assert report["v44_new_real_probe_count"] == 0
    assert report["v44_new_real_scored_count"] == 0
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["gate_visible_in_runtime_process"] is False


def test_v44_enabled_runs_bounded_lane_isolated_scaleout_without_execution() -> None:
    transport = ObserverScaleoutReadOnlyTransport()
    reports = v44_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=transport)
    report = reports["v44_readonly_observer_scaleout_controller_v1_report.json"]
    assert report["observer_scaleout_status"] == "PASS_READONLY_OBSERVER_SCALEOUT"
    assert report["max_observer_lanes"] == 3
    assert report["max_cycles_per_lane"] == 2
    assert report["max_total_requests"] == 18
    assert 9 <= report["v44_new_real_scored_count"] <= 18
    assert 36 <= report["cumulative_real_scored_count"] <= 45
    assert report["calibration_tier"] == "DEVELOPING_SAMPLE"
    assert report["stable_sample_candidate_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert report["observer_lane_isolation_status"] == "PASS"
    assert report["source_rotation_status"] == "PASS"
    assert report["execution_lock_v3_status"] == "PASS"
    assert report["live_trading_readiness_claim"] is False
    assert len(transport.calls) <= 18


def test_v44_fuzzy_ack_blocks_probe_run() -> None:
    reports = v44_reports(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY "}, enable_real_probe=True, real_transport=ObserverScaleoutReadOnlyTransport())
    report = reports["exact_gate_runtime_v12_report.json"]
    assert report["exact_gate_status"] == "PROBE_DISABLED_BY_DEFAULT"
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["v44_new_real_probe_count"] == 0
