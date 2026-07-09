from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_dummy_mission_state_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["autonomous_workflow_kernel_status"] == "PASS"
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["real_evidence_count"] == 0
    assert report["observed_count"] == 0
    assert report["live_scored_count"] == 0
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
