from __future__ import annotations


def test_no_caps_config_modification_v17_report_passes() -> None:
    from archive.report_scripts.generate_v17_reports import generate_no_caps_config_modification_report_v17

    assert generate_no_caps_config_modification_report_v17()["verdict"] == "PASS"
