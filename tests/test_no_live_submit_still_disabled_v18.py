from __future__ import annotations


def test_no_live_submit_still_disabled_v18_report_passes() -> None:
    from scripts.generate_v18_reports import generate_no_live_submit_still_disabled_report_v18

    report = generate_no_live_submit_still_disabled_report_v18()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
