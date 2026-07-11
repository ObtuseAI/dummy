from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_no_direct_order_bypass_report_v12


def test_no_direct_order_bypass_v12() -> None:
    report = generate_no_direct_order_bypass_report_v12()

    assert report["verdict"] == "PASS"
    assert report["unexpected_caller_qualnames"] == []
