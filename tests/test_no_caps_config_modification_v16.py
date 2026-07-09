from __future__ import annotations


def test_no_caps_config_modification_v16_report_passes() -> None:
    from scripts.generate_v16_reports import generate_no_caps_config_modification_report_v16

    assert generate_no_caps_config_modification_report_v16()["verdict"] == "PASS"
