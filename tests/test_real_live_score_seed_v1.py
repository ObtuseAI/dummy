from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_live_score_seed_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_pnl_claim"] is True
    assert report["no_trading_readiness_claim"] is True
    assert report["execution_bridge_present"] is False
