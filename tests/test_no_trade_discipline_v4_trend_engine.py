from __future__ import annotations

from tests.v43_test_helpers import assert_current_test_report


def test_no_trade_discipline_v4_trend_engine_report() -> None:
    assert_current_test_report(__file__)
