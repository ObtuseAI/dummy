from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_market_class_real_sample_scoreboard_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["market_class_scoreboard_status"] == "PASS"
    assert "weather" in report["market_classes"]
    assert "crypto" in report["market_classes"]
    assert "public_event_reference" in report["market_classes"]
    assert report["sports_fixture_only_excluded"] is True
    assert report["live_trading_recommendation"] is False
