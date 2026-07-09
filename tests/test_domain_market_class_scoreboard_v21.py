from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_domain_market_class_scoreboard_v21() -> None:
    report = assert_current_test_report(__file__)
    assert "rows" in report
    assert report["execution_bridge_present"] is False
