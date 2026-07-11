from __future__ import annotations

from archive.report_scripts.generate_v10_reports import generate_no_unauthorized_source_report_v10


def test_no_unauthorized_source_v10() -> None:
    report = generate_no_unauthorized_source_report_v10()
    assert report["verdict"] == "PASS"
    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping"] is False
