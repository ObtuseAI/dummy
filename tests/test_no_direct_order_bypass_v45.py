from __future__ import annotations
from tests.v45_test_helpers import assert_current_test_report
def test_no_direct_order_bypass_v45_report() -> None:
    assert_current_test_report(__file__)
