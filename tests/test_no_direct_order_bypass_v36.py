from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_no_direct_order_bypass_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["execution_bridge_present"] is False
