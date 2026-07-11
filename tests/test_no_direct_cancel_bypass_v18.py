from __future__ import annotations


def test_no_direct_cancel_bypass_v18_report_passes() -> None:
    from archive.report_scripts.generate_v18_reports import generate_no_direct_cancel_bypass_report_v18

    report = generate_no_direct_cancel_bypass_report_v18()
    assert report["unexpected_cancel_callers"] == []
    assert report["verdict"] == "PASS"
