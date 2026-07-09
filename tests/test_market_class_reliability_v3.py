from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_market_class_reliability_v3_assigns_readonly_reliability_classes() -> None:
    report = assert_current_test_report(__file__)
    assert report["market_class_reliability_v3_status"] == "PASS"
    assert "EARLY_DIAGNOSTIC" in report["reliability_classes"]
    assert report["sports_fixture_only_excluded"] is True
    assert report["live_trading_recommendation"] is False
