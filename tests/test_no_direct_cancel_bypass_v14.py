from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_no_direct_cancel_bypass_report_v14


def test_no_direct_cancel_bypass_v14_report_passes() -> None:
    report = generate_no_direct_cancel_bypass_report_v14()

    assert report["verdict"] == "PASS"
    assert report["unexpected_cancel_callers"] == []
    assert report["rehearsal_cancel_only"] is True
