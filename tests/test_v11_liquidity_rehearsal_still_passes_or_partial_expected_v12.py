from __future__ import annotations

from scripts.generate_v12_reports import generate_v11_liquidity_status_report_v12


def test_v11_liquidity_rehearsal_still_passes_or_partial_expected_v12() -> None:
    report = generate_v11_liquidity_status_report_v12()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    if report["verdict"] == "PARTIAL":
        assert "orderbook_liquidity_model_report_v1.json" in report["expected_partials"]
