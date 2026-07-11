from __future__ import annotations

from archive.report_scripts.generate_v13_reports import generate_no_direct_cancel_bypass_report_v13


def test_no_direct_cancel_bypass_v13_report_passes() -> None:
    report = generate_no_direct_cancel_bypass_report_v13()

    assert report["verdict"] == "PASS"
    assert report["unexpected_cancel_callers"] == []
