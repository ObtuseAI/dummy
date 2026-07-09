from __future__ import annotations

from scripts.generate_v9_reports import generate_no_live_submit_still_disabled_report_v9


def test_live_submit_still_disabled_v9() -> None:
    report = generate_no_live_submit_still_disabled_report_v9()
    assert report["enabled"] is False
    assert report["verdict"] == "PASS"
