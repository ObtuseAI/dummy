from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_readiness_ladder_v1_keeps_rehearsal_and_live_trading_locked() -> None:
    report = assert_current_test_report(__file__)
    assert report["readiness_ladder_status"] == "PASS"
    assert "LIVE_TRADING_LOCKED" in report["readiness_stages"]
    assert report["operator_armed_rehearsal_locked"] is True
    assert report["live_trading_locked"] is True
