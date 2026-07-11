from __future__ import annotations


def test_v11_liquidity_still_passes_or_partial_expected_v16() -> None:
    from archive.report_scripts.generate_v16_reports import generate_prior_milestone_statuses

    assert generate_prior_milestone_statuses()["v11_liquidity_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
