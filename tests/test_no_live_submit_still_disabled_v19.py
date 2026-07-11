from __future__ import annotations


def test_no_live_submit_still_disabled_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_no_live_submit_still_disabled_report_v19

    report = generate_no_live_submit_still_disabled_report_v19()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
