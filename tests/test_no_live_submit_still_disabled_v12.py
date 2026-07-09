from __future__ import annotations

from scripts.generate_v12_reports import generate_no_live_submit_still_disabled_report_v12


def test_no_live_submit_still_disabled_v12() -> None:
    report = generate_no_live_submit_still_disabled_report_v12()

    assert report["enabled"] is False
    assert report["config_diff_empty"] is True
    assert report["verdict"] == "PASS"
