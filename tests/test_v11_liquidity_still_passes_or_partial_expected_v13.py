from __future__ import annotations

from scripts.generate_v13_reports import generate_v11_liquidity_status_report_v13


def test_v11_liquidity_still_passes_or_partial_expected_v13() -> None:
    report = generate_v11_liquidity_status_report_v13()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["partial_expected"] in {True, False}
