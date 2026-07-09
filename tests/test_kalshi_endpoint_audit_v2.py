"""Tests for the V2 Kalshi endpoint audit report."""

import os

import pytest


@pytest.mark.asyncio
async def test_kalshi_endpoint_audit_report_v2():
    from scripts.generate_v8_kalshi_reports import generate_kalshi_endpoint_audit_report_v2

    report = await generate_kalshi_endpoint_audit_report_v2()
    assert report["verdict"] in ("PASS", "SKIP")
    assert "entries" in report
    assert "summary" in report
    assert "order_endpoints_called" in report
    assert "write_endpoints_called" in report
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
        assert isinstance(report["entries"], list)
        assert report["order_endpoints_called"] == []
    else:
        assert report["credentials_present"] is False


@pytest.mark.asyncio
async def test_kalshi_endpoint_audit_no_write_methods_when_credentials_absent():
    from scripts.generate_v8_kalshi_reports import generate_kalshi_endpoint_audit_report_v2

    report = await generate_kalshi_endpoint_audit_report_v2()
    if not os.environ.get("KALSHI_API_KEY_ID"):
        assert report["write_endpoints_called"] == []
        assert report["order_endpoints_called"] == []
