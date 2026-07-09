from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v45_test_helpers import ObserverContinuationReadOnlyTransport, v45_reports


def test_v45_controller_default_blocks_without_gate() -> None:
    reports = v45_reports()
    report = reports["v45_readonly_observer_continuation_controller_v1_report.json"]
    assert report["observer_continuation_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v44_cumulative_real_scored_count"] >= 45
    assert report["v45_new_real_probe_count"] == 0
    assert report["v45_new_real_scored_count"] == 0
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["gate_visible_in_runtime_process"] is False


def test_v45_enabled_runs_bounded_continuation_without_unlocking_stable_sample() -> None:
    transport = ObserverContinuationReadOnlyTransport()
    reports = v45_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=transport)
    report = reports["v45_readonly_observer_continuation_controller_v1_report.json"]
    assert report["observer_continuation_status"] == "PASS_READONLY_OBSERVER_CONTINUATION"
    assert report["max_observer_lanes"] == 4
    assert report["max_cycles_per_lane"] == 2
    assert report["max_total_requests"] == 30
    assert 15 <= report["v45_new_real_scored_count"] <= 30
    assert 60 <= report["cumulative_real_scored_count"] <= 75
    assert report["calibration_tier"] == "DEVELOPING_SAMPLE"
    assert report["stable_sample_prep_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert report["observer_lane_continuation_status"] == "PASS"
    assert report["source_portfolio_status"] == "PASS"
    assert report["execution_lock_v4_status"] == "PASS"
    assert report["stable_sample_candidate_live_trading_readiness_claim"] is False
    assert len(transport.calls) <= 30


def test_v45_fuzzy_ack_blocks_probe_run() -> None:
    reports = v45_reports(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY "}, enable_real_probe=True, real_transport=ObserverContinuationReadOnlyTransport())
    report = reports["exact_gate_runtime_v13_report.json"]
    assert report["exact_gate_status"] == "PROBE_DISABLED_BY_DEFAULT"
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["v45_new_real_probe_count"] == 0
