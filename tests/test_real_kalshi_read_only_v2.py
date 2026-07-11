import os
import pytest


def test_real_kalshi_read_only_no_order_endpoints():
    from kalshi.live_data import KalshiRealReadOnly
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /portfolio/balance",
        "GET /events",
        "GET /markets",
        "GET /markets/MKT/orderbook",
        "GET /portfolio/positions",
        "GET /portfolio/orders",
        "GET /portfolio/fills",
    }
    assert not reader.order_creating_endpoints_called()


@pytest.mark.asyncio
async def test_read_only_report_status():
    from archive.report_scripts.generate_v5_reports import generate_real_kalshi_read_only_report_v2
    report = await generate_real_kalshi_read_only_report_v2()
    assert report["verdict"] in ("PASS", "SKIP")
    if os.environ.get("KALSHI_API_KEY_ID"):
        assert report["credentials_present"] is True
    else:
        assert report["credentials_present"] is False
