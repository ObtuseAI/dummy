from __future__ import annotations

from scripts.generate_v13_reports import generate_no_caps_config_modification_report_v13


def test_no_caps_config_modification_v13_report_passes() -> None:
    report = generate_no_caps_config_modification_report_v13()

    assert report["modified_by_v13"] is False
    assert report["verdict"] == "PASS"
