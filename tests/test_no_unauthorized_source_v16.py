from __future__ import annotations


def test_no_unauthorized_source_v16_report_passes() -> None:
    from archive.report_scripts.generate_v16_reports import generate_no_unauthorized_source_report_v16

    assert generate_no_unauthorized_source_report_v16()["verdict"] == "PASS"
