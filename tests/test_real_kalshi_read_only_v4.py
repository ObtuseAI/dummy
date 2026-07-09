"""Tests for the V4 real Kalshi READ_ONLY report."""

import os

import pytest


@pytest.mark.asyncio
async def test_real_kalshi_read_only_report_v4():
    from scripts.generate_v8_kalshi_reports import generate_real_kalshi_read_only_report_v4

    report = await generate_real_kalshi_read_only_report_v4()
    assert report["verdict"] in ("PASS", "SKIP")
    assert "endpoints_called" in report
    assert "order_creating_endpoints_called" in report
    assert "write_http_methods_used" in report
    assert "data_summary" in report
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
        assert report["order_creating_endpoints_called"] == []
        assert report["write_http_methods_used"] == []
    else:
        assert report["credentials_present"] is False


@pytest.mark.asyncio
async def test_real_kalshi_read_only_report_no_secrets():
    from scripts.generate_v8_kalshi_reports import generate_real_kalshi_read_only_report_v4

    report = await generate_real_kalshi_read_only_report_v4()
    text = str(report)
    secret_markers = ["KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM", "-----BEGIN"]
    assert not any(marker in text for marker in secret_markers)
