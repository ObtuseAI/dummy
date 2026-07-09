from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_dummy_mission_state_v41_carries_statuses_and_safety() -> None:
    report = assert_current_test_report(__file__)
    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["v40_carried_status"] == "PASS"
    assert report["v40_baseline_status"] == "PASS_V40_BASELINE_READBACK"
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["no_execution_bridge_status"] == "PASS"
