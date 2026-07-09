from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_market_class_scoreboard_v2_includes_counts_and_no_recommendation() -> None:
    report = assert_current_test_report(__file__)
    assert report["market_class_scoreboard_v2_status"] == "PASS"
    assert "weather" in report["market_classes"]
    assert report["sports_fixture_only_excluded"] is True
    assert report["live_trading_recommendation"] is False
