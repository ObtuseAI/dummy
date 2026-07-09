from __future__ import annotations


def test_no_secret_leak_v16_report_passes() -> None:
    from scripts.generate_v16_reports import generate_no_secret_leak_report_v16

    assert generate_no_secret_leak_report_v16()["verdict"] == "PASS"
