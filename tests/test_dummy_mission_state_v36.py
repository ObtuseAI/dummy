from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_dummy_mission_state_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["no_browser_automation"] is True
    assert report["no_mined_code"] is True
    assert report["v35_fail_escalation_preserved"] is True
    assert report["execution_bridge_present"] is False
