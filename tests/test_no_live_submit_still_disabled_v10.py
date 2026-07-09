from __future__ import annotations

from scripts.generate_v10_reports import generate_no_live_submit_still_disabled_report_v10


def test_live_submit_still_disabled_v10() -> None:
    report = generate_no_live_submit_still_disabled_report_v10()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
