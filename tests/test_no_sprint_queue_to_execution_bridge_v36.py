from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_no_sprint_queue_to_execution_bridge_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_live_trading_task"] is True
    assert report["no_browser_task"] is True
    assert report["no_mined_code_task"] is True
    assert report["execution_bridge_present"] is False
