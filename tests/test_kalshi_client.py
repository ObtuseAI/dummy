import pytest, os
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
