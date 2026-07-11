from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_no_unauthorized_source_report_v14


def test_no_unauthorized_source_v14_report_passes() -> None:
    report = generate_no_unauthorized_source_report_v14()

    assert report["unauthorized_sources"] == []
    assert report["private_or_insider_data_used"] is False
    assert report["verdict"] == "PASS"
