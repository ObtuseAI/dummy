from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_timeout_guards_still_intact_report_v14


def test_timeout_guards_still_intact_v14_report_passes() -> None:
    report = generate_timeout_guards_still_intact_report_v14()

    assert report["kalshi_request_timeout_s"] <= 10.0
    assert report["recursive_pytest_allowed"] is False
    assert report["verdict"] == "PASS"
