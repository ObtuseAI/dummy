from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_v10_acceleration_status_report_v11


def test_v10_acceleration_still_passes_or_partial_expected_v11() -> None:
    report = generate_v10_acceleration_status_report_v11()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["v10_status"] in {"PASS", "PARTIAL"}
    if report["v10_status"] == "PARTIAL":
        assert report["partial_reason"] == "sample_or_mock_adapters_remaining"
