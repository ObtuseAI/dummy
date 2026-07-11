from __future__ import annotations

from archive.report_scripts.generate_v13_reports import generate_no_live_submit_still_disabled_report_v13


def test_no_live_submit_still_disabled_v13_report_passes() -> None:
    report = generate_no_live_submit_still_disabled_report_v13()

    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
