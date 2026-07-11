from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_v10_acceleration_status_report_v14


def test_v10_acceleration_still_passes_or_partial_expected_v14() -> None:
    report = generate_v10_acceleration_status_report_v14()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["partial_expected"] in {True, False}
