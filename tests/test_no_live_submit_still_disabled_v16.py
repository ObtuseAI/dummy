from __future__ import annotations


def test_no_live_submit_still_disabled_v16_report_passes() -> None:
    from archive.report_scripts.generate_v16_reports import generate_no_live_submit_still_disabled_report_v16

    report = generate_no_live_submit_still_disabled_report_v16()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
