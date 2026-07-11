from __future__ import annotations


def test_no_direct_order_bypass_v16_report_passes() -> None:
    from archive.report_scripts.generate_v16_reports import generate_no_direct_order_bypass_report_v16

    report = generate_no_direct_order_bypass_report_v16()
    assert report["verdict"] == "PASS"
    assert report["unexpected_order_callers"] == []
