from __future__ import annotations

from scripts.generate_v10_reports import generate_no_direct_order_bypass_report_v10


def test_no_direct_order_bypass_v10() -> None:
    report = generate_no_direct_order_bypass_report_v10()
    assert report["verdict"] == "PASS"
    assert report["unexpected_caller_qualnames"] == []
