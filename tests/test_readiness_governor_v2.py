from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_readiness_governor_v2_keeps_trading_locked() -> None:
    report = assert_current_test_report(__file__)
    assert report["readiness_governor_status"] == "PASS"
    assert "LIVE_TRADING_LOCKED" in report["readiness_stages"]
    assert report["live_trading_locked"] is True
    assert report["readiness_governor_to_execution_bridge_present"] is False
