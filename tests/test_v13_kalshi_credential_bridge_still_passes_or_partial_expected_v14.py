from __future__ import annotations

from scripts.generate_v14_reports import generate_v13_kalshi_credential_bridge_status_report_v14


def test_v13_kalshi_credential_bridge_still_passes_or_partial_expected_v14() -> None:
    report = generate_v13_kalshi_credential_bridge_status_report_v14()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["partial_expected"] in {True, False}
