from __future__ import annotations

from archive.report_scripts.generate_v9_reports import generate_no_secret_leak_report_v9


def test_no_secret_leak_report_v9_passes() -> None:
    report = generate_no_secret_leak_report_v9()
    assert report["verdict"] == "PASS"
    assert report["sample_values_redacted"] is True
    assert report["leaked_files"] == []
