import pytest, os, httpx
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from kalshi.client import KalshiClient
from kalshi.signer import sign_request
from kalshi.error_classifier import classify, KalshiErrorCategory

@pytest.fixture
def client():
    return KalshiClient()

@pytest.mark.asyncio
async def test_sign_request_requires_key_id():
    os.environ.pop("KALSHI_API_KEY_ID", None)
    with pytest.raises(RuntimeError):
        sign_request("GET", "/markets")

@pytest.mark.asyncio
async def test_get_orderbook_parsing(client):
    mock_resp = {"orderbook": {"bids": [{"price": 50, "count": 10}], "asks": [{"price": 55, "count": 5}]}}
    with patch("kalshi.client.sign_request", return_value={"KALSHI-ACCESS-KEY": "test", "KALSHI-ACCESS-SIGNATURE": "sig", "KALSHI-ACCESS-TIMESTAMP": "ts"}) as _:
        with patch.object(client.client, "request", new_callable=AsyncMock) as m:
            m.return_value.status_code = 200
            m.return_value.json = MagicMock(return_value=mock_resp)
            m.return_value.raise_for_status = MagicMock()
            ob = await client.get_orderbook("MARKET")
            assert ob.bids[0].price == 50
            assert ob.asks[0].size == 5

def test_error_classifier_rate_limit():
    assert classify(429, "") == KalshiErrorCategory.RATE_LIMIT

def test_error_classifier_auth():
    assert classify(401, "") == KalshiErrorCategory.AUTH

@pytest.mark.asyncio
async def test_create_order_signs_json_body(client):
    order = {"ticker": "MARKET", "side": "yes", "count": 10, "price": 50}
    expected_body = '{"count":10,"price":50,"side":"yes","ticker":"MARKET"}'
    with patch("kalshi.client.sign_request") as mock_sign:
        with patch.object(client.client, "request", new_callable=AsyncMock) as m:
            m.return_value.status_code = 200
            m.return_value.json = MagicMock(return_value={"status": "success"})
            m.return_value.raise_for_status = MagicMock()
            await client.create_order(order)
            mock_sign.assert_called_once()
            signed_body = mock_sign.call_args[0][2]
            assert signed_body == expected_body
            m.assert_called_once()
            assert m.call_args.kwargs.get("content") == expected_body.encode("utf-8")
            assert "json" not in m.call_args.kwargs

@pytest.mark.asyncio
async def test_rate_limiter_retries_connect_error(client):
    client.limiter.base_delay = 0
    with patch("kalshi.client.sign_request", return_value={"KALSHI-ACCESS-KEY": "test", "KALSHI-ACCESS-SIGNATURE": "sig", "KALSHI-ACCESS-TIMESTAMP": "ts"}) as _:
        with patch.object(client.client, "request", new_callable=AsyncMock) as m:
            m.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(httpx.ConnectError):
                await client.get_markets()
            assert m.call_count == client.limiter.max_retries + 1
