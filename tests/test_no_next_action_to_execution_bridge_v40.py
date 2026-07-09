from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_next_action_to_execution_bridge_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["next_action_to_execution_bridge_present"] is False
    assert report["selected_action_can_trigger_execution"] is False
    assert report["selected_next_action"] != "LIVE_TRADING"
