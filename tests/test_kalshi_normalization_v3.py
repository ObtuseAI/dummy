import os
import pytest


@pytest.mark.asyncio
async def test_kalshi_normalization_report_v3():
    from scripts.generate_v6_reports import generate_kalshi_normalization_report_v3
    report = await generate_kalshi_normalization_report_v3()
    assert report["verdict"] in ("PASS", "SKIP", "MOCK_ONLY", "FAIL")
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
    else:
        assert report["credentials_present"] is False


@pytest.mark.asyncio
async def test_real_market_snapshot_manifest_v1():
    from scripts.generate_v6_reports import generate_real_market_snapshot_manifest_v1
    report = await generate_real_market_snapshot_manifest_v1()
    assert report["verdict"] in ("PASS", "SKIP", "MOCK_ONLY", "FAIL")
    assert "normalized_counts" in report
