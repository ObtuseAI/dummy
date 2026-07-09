from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_dispatch_overlap_fix_verified() -> None:
    report = assert_current_test_report(__file__)
    assert report["dispatch_overlap_fixed"] is True
    assert report["budget_reports_isolated"] is True
    assert report["scoreboard_reports_isolated"] is True
    assert report["growth_queue_reports_isolated"] is True
    assert report["execution_bridge_present"] is False
