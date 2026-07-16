from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_direct_order_bypass_v20_report_passes() -> None:
    report = assert_security_report("generate_no_direct_order_bypass_report_v20")
    assert report["unexpected_order_callers"] == []
