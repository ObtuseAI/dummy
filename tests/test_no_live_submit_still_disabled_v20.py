from __future__ import annotations


def test_no_live_submit_still_disabled_v20_report_passes() -> None:
    from archive.report_scripts.generate_v20_reports import generate_no_live_submit_still_disabled_report_v20

    report = generate_no_live_submit_still_disabled_report_v20()

    assert report["verdict"] == "PASS"
    assert report["enabled"] is False
    assert report["modified_by_v20"] is False
