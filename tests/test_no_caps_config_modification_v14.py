from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_no_caps_config_modification_report_v14


def test_no_caps_config_modification_v14_report_passes() -> None:
    report = generate_no_caps_config_modification_report_v14()

    assert report["modified_by_v14"] is False
    assert report["verdict"] == "PASS"
