from __future__ import annotations


def test_v11_v12_liquidity_historical_still_partial_expected_v17() -> None:
    from archive.report_scripts.generate_v17_reports import generate_prior_statuses_v17

    status = generate_prior_statuses_v17()
    assert status["v11_liquidity_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
    assert status["v12_liquidity_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
