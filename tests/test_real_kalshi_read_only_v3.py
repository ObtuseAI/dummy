import os
import pytest


@pytest.mark.asyncio
async def test_real_kalshi_read_only_report_v3():
    from scripts.generate_v6_reports import generate_real_kalshi_read_only_report_v3
    report = await generate_real_kalshi_read_only_report_v3()
    assert report["verdict"] in ("PASS", "SKIP")
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
        assert report["order_creating_endpoints_called"] == []
    else:
        assert report["credentials_present"] is False


@pytest.mark.asyncio
async def test_no_order_endpoints_in_read_only_v3():
    from kalshi.live_data import KalshiRealReadOnly
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /portfolio/balance",
        "GET /events",
        "GET /markets",
        "GET /markets/{ticker}/orderbook",
        "GET /portfolio/positions",
        "GET /portfolio/orders",
        "GET /portfolio/fills",
    }
    assert not reader.order_creating_endpoints_called()
