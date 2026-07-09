from __future__ import annotations

from scripts.generate_v13_reports import generate_timeout_guards_still_intact_report_v13


def test_timeout_guards_still_intact_v13_report_passes() -> None:
    report = generate_timeout_guards_still_intact_report_v13()

    assert report["verdict"] == "PASS"
    assert report["kalshi_request_timeout_s"] <= 10
    assert report["kalshi_total_discovery_timeout_s"] <= 45
