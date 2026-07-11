from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_no_live_submit_still_disabled_report_v11


def test_no_live_submit_still_disabled_v11() -> None:
    report = generate_no_live_submit_still_disabled_report_v11()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
