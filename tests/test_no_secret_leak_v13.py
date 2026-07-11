from __future__ import annotations

from archive.report_scripts.generate_v13_reports import generate_no_secret_leak_report_v13


def test_no_secret_leak_v13_report_passes() -> None:
    report = generate_no_secret_leak_report_v13()

    assert report["verdict"] == "PASS"
    assert report["leaked_files"] == []
