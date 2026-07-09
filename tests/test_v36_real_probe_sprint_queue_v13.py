from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_v36_real_probe_sprint_queue_v13() -> None:
    report = assert_current_test_report(__file__)
    assert report["sports_legal_first"] is True
    assert report["no_live_trading_work_item"] is True
    assert report["no_browser_or_mined_code_work_item"] is True
    assert report["execution_bridge_present"] is False
