from __future__ import annotations


def test_no_secret_leak_v18_report_passes() -> None:
    from scripts.generate_v18_reports import generate_no_secret_leak_report_v18

    assert generate_no_secret_leak_report_v18()["verdict"] == "PASS"
