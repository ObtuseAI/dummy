from __future__ import annotations

from archive.report_scripts.generate_v8_2_reports import generate_direct_order_bypass_report_v8_2


def test_direct_order_bypass_report_v8_2_passes():
    report = generate_direct_order_bypass_report_v8_2()
    assert report["verdict"] == "PASS"
    assert report["violations"] == []
