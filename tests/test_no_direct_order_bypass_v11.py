from __future__ import annotations

from scripts.generate_v11_reports import generate_no_direct_order_bypass_report_v11


def test_no_direct_order_bypass_v11() -> None:
    report = generate_no_direct_order_bypass_report_v11()
    assert report["verdict"] == "PASS"
    assert report["unexpected_caller_qualnames"] == []
