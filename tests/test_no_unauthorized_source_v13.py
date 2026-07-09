from __future__ import annotations

from scripts.generate_v13_reports import generate_no_unauthorized_source_report_v13


def test_no_unauthorized_source_v13_report_passes() -> None:
    report = generate_no_unauthorized_source_report_v13()

    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping"] is False
    assert report["verdict"] == "PASS"
