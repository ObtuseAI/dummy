from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v46_test_helpers import ThresholdPursuitReadOnlyTransport, v46_reports


def test_v46_controller_default_blocks_without_gate() -> None:
    reports = v46_reports()
    report = reports["v46_readonly_observer_threshold_pursuit_controller_v1_report.json"]
    assert report["observer_threshold_pursuit_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v45_cumulative_real_scored_count"] >= 63
    assert report["v46_new_real_probe_count"] == 0
    assert report["v46_new_real_scored_count"] == 0
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["gate_visible_in_runtime_process"] is False


def test_v46_enabled_runs_bounded_threshold_pursuit_without_unlocking_stable_sample() -> None:
    transport = ThresholdPursuitReadOnlyTransport()
    reports = v46_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=transport)
    report = reports["v46_readonly_observer_threshold_pursuit_controller_v1_report.json"]
    assert report["observer_threshold_pursuit_status"] == "PASS_READONLY_OBSERVER_THRESHOLD_PURSUIT"
    assert report["max_observer_lanes"] == 4
    assert report["max_cycles_per_lane"] == 3
    assert report["max_total_requests"] == 36
    assert 18 <= report["v46_new_real_scored_count"] <= 30
    assert 81 <= report["cumulative_real_scored_count"] <= 93
    assert report["score_gap_to_100"] > 0
    assert report["calibration_tier"] == "DEVELOPING_SAMPLE"
    assert report["stable_sample_gap_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert report["observer_lane_health_status"] == "PASS"
    assert report["source_portfolio_status"] == "PASS"
    assert report["execution_lock_v5_status"] == "PASS"
    assert report["stable_sample_candidate_live_trading_readiness_claim"] is False
    assert len(transport.calls) <= 36


def test_v46_fuzzy_ack_blocks_probe_run() -> None:
    reports = v46_reports(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY "}, enable_real_probe=True, real_transport=ThresholdPursuitReadOnlyTransport())
    report = reports["exact_gate_runtime_v14_report.json"]
    assert report["exact_gate_status"] == "PROBE_DISABLED_BY_DEFAULT"
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["v46_new_real_probe_count"] == 0
