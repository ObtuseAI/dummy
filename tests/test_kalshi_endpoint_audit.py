import os
import pytest


@pytest.mark.asyncio
async def test_kalshi_endpoint_audit_report_v1():
    from archive.report_scripts.generate_v6_reports import generate_kalshi_endpoint_audit_report_v1
    report = await generate_kalshi_endpoint_audit_report_v1()
    assert report["verdict"] in ("PASS", "SKIP")
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
        assert "summary" in report
        assert isinstance(report["entries"], list)
    else:
        assert report["credentials_present"] is False
