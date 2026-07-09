from __future__ import annotations

from scripts.generate_v14_reports import generate_no_live_submit_still_disabled_report_v14


def test_no_live_submit_still_disabled_v14_report_passes() -> None:
    report = generate_no_live_submit_still_disabled_report_v14()

    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
