from __future__ import annotations

from scripts.generate_v12_reports import generate_v10_acceleration_status_report_v12


def test_v10_acceleration_still_passes_or_partial_expected_v12() -> None:
    report = generate_v10_acceleration_status_report_v12()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    if report["verdict"] == "PARTIAL":
        assert report["partial_reason"] == "sample_or_mock_adapters_remaining"
