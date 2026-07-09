import os
import pytest


@pytest.mark.asyncio
async def test_real_market_strategy_scan_report_v3():
    from scripts.generate_v6_reports import generate_real_market_strategy_scan_report_v3
    report = await generate_real_market_strategy_scan_report_v3()
    assert report["verdict"] in ("PASS", "SKIP", "FAIL")
    assert report["repo_derived_families_evaluated"] > 0
    for r in report.get("results", []):
        assert "family" in r
        assert "edge_estimate" in r
        assert "confidence" in r
