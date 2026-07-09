from __future__ import annotations

from scripts.generate_v8_2_reports import generate_no_live_submit_still_disabled_report_v8_2


def test_live_submit_still_disabled_v8_2():
    report = generate_no_live_submit_still_disabled_report_v8_2()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
