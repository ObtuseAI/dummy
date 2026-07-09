from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_dummy_mission_state_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["v39_baseline_status"] == "PASS_V39_BASELINE_READBACK"
    assert report["v39_baseline_real_scored_count"] >= 3
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"


def test_dummy_mission_state_v40_enabled_expands_sample() -> None:
    report = v40_enabled_reports()["dummy_mission_state_report_v26.json"]
    assert report["mission_state_verdict"] == "PASS"
    assert report["v40_new_real_scored_count"] > 0
    assert report["cumulative_real_scored_count"] > report["v39_baseline_real_scored_count"]
    assert report["source_truth_v21_status"] == "PASS"
