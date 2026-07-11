from __future__ import annotations


def test_no_live_submit_still_disabled_v17_report_passes() -> None:
    from archive.report_scripts.generate_v17_reports import generate_no_live_submit_still_disabled_report_v17

    report = generate_no_live_submit_still_disabled_report_v17()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
