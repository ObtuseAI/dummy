from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_no_caps_config_modification_report_v12


def test_no_caps_config_modification_v12() -> None:
    report = generate_no_caps_config_modification_report_v12()

    assert report["config_diff_empty"] is True
    assert report["verdict"] == "PASS"
