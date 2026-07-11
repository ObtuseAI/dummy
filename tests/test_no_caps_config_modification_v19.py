from __future__ import annotations


def test_no_caps_config_modification_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_no_caps_config_modification_report_v19

    assert generate_no_caps_config_modification_report_v19()["verdict"] == "PASS"
