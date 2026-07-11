from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_no_caps_config_modification_report_v11


def test_no_caps_config_modification_v11() -> None:
    report = generate_no_caps_config_modification_report_v11()
    assert report["verdict"] == "PASS"
    assert report["modified_by_v11"] is False
