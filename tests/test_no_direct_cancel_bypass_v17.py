from __future__ import annotations


def test_no_direct_cancel_bypass_v17_report_passes() -> None:
    from scripts.generate_v17_reports import generate_no_direct_cancel_bypass_report_v17

    report = generate_no_direct_cancel_bypass_report_v17()
    assert report["verdict"] == "PASS"
    assert report["unexpected_cancel_callers"] == []
