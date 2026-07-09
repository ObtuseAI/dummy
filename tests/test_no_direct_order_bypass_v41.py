from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_direct_order_bypass_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["direct_order_bypass_present"] is False
    assert report["direct_cancel_bypass_present"] is False
