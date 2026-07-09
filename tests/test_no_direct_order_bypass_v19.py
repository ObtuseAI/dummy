from __future__ import annotations


def test_no_direct_order_bypass_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_no_direct_order_bypass_report_v19

    report = generate_no_direct_order_bypass_report_v19()
    assert report["unexpected_order_callers"] == []
    assert report["verdict"] == "PASS"
