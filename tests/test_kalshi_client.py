import pytest
import os
import httpx
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock
from kalshi.client import KalshiClient, _CENTRAL_FIREWALL_SUBMIT_CAPABILITY
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
            assert ob.source_ts is None
            assert ob.received_at is not None
            assert ob.timestamp == ob.received_at
            assert ob.freshness_score == Decimal("1.0")


@pytest.mark.asyncio
async def test_get_orderbook_sorts_and_rejects_missing_book(client):
    with patch("kalshi.client.sign_request", return_value={"KALSHI-ACCESS-KEY": "test", "KALSHI-ACCESS-SIGNATURE": "sig", "KALSHI-ACCESS-TIMESTAMP": "ts"}):
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            request.return_value.status_code = 200
            request.return_value.raise_for_status = MagicMock()
            request.return_value.json = MagicMock(return_value={"orderbook": {"bids": [{"price": 48, "count": 1}, {"price": 40, "count": 1}], "asks": [{"price": 60, "count": 1}, {"price": 52, "count": 1}]}})
            book = await client.get_orderbook("MARKET")
            assert [level.price for level in book.bids] == [40, 48]
            assert [level.price for level in book.asks] == [52, 60]

            request.return_value.json = MagicMock(return_value={"orderbook": {}})
            with pytest.raises(ValueError, match="missing"):
                await client.get_orderbook("MARKET")

def test_error_classifier_rate_limit():
    assert classify(429, "") == KalshiErrorCategory.RATE_LIMIT

def test_error_classifier_auth():
    assert classify(401, "") == KalshiErrorCategory.AUTH

def test_error_classifier_body_specific_400s():
    assert classify(400, {"error": "market is closed"}) == KalshiErrorCategory.MARKET_CLOSED
    assert classify(400, {"error": "insufficient funds"}) == KalshiErrorCategory.INSUFFICIENT_FUNDS

@pytest.mark.asyncio
async def test_get_markets_accumulates_bounded_pages(client):
    pages = [
        {"markets": [{"ticker": "A"}], "cursor": "next"},
        {"markets": [{"ticker": "B"}], "cursor": None},
    ]
    with patch.object(client, "_request", new=AsyncMock(side_effect=pages)) as request:
        result = await client.get_markets(max_pages=3)
    assert [market["ticker"] for market in result["markets"]] == ["A", "B"]
    assert result["pagination_truncated"] is False
    assert request.await_args_list[0].kwargs["params"] == {"status": "open"}
    assert request.await_args_list[1].kwargs["params"] == {"status": "open", "cursor": "next"}

@pytest.mark.asyncio
async def test_get_markets_reports_pagination_truncation(client):
    with patch.object(
        client,
        "_request",
        new=AsyncMock(return_value={"markets": [{"ticker": "A"}], "cursor": "more"}),
    ):
        result = await client.get_markets(max_pages=1)
    assert result["pagination_truncated"] is True

@pytest.mark.asyncio
async def test_create_order_signs_json_body(client):
    order = {"ticker": "MARKET", "side": "yes", "count": 10, "price": 50}
    expected_body = '{"count":10,"price":50,"side":"yes","ticker":"MARKET"}'
    with patch("kalshi.client.sign_request") as mock_sign:
        with patch.object(client.client, "request", new_callable=AsyncMock) as m:
            m.return_value.status_code = 200
            m.return_value.json = MagicMock(return_value={"status": "success"})
            m.return_value.raise_for_status = MagicMock()
            await client.create_order(
                order,
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
            mock_sign.assert_called_once()
            signed_body = mock_sign.call_args[0][2]
            assert signed_body == expected_body
            m.assert_called_once()
            assert m.call_args.kwargs.get("content") == expected_body.encode("utf-8")
            assert "json" not in m.call_args.kwargs


@pytest.mark.asyncio
async def test_direct_create_order_without_central_capability_fails_before_transport(client):
    with patch.object(client, "_request", new=AsyncMock()) as request:
        with pytest.raises(
            PermissionError,
            match="DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL",
        ):
            await client.create_order({"ticker": "MARKET"})
    request.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/portfolio/orders"),
        ("post", "/portfolio/orders?client_order_id=ignored"),
        ("PATCH", "/portfolio/orders/order-123"),
        (
            "DELETE",
            "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders/order-123",
        ),
        ("PUT", r"\portfolio\orders\order-123"),
        ("POST", "/portfolio%252Forders"),
        ("POST", "/portfolio/ignored/../orders"),
        ("PURGE", "/portfolio/orders/order-123"),
    ],
)
@pytest.mark.asyncio
async def test_direct_raw_order_mutations_fail_before_signing_or_transport(
    client,
    method,
    path,
):
    with patch("kalshi.client.sign_request") as sign_request:
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            with pytest.raises(
                PermissionError,
                match="DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL",
            ):
                await client._request(method, path, json={"ticker": "MARKET"})
    sign_request.assert_not_called()
    request.assert_not_awaited()


@pytest.mark.asyncio
async def test_raw_order_mutation_rejects_forged_capability_before_transport(client):
    with patch("kalshi.client.sign_request") as sign_request:
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            with pytest.raises(
                PermissionError,
                match="DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL",
            ):
                await client._request(
                    "POST",
                    "/portfolio/orders",
                    json={"ticker": "MARKET"},
                    _capability=object(),
                )
    sign_request.assert_not_called()
    request.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_raw_order_mutation_consumes_capability_locally(client):
    with patch(
        "kalshi.client.sign_request",
        return_value={
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "sig",
            "KALSHI-ACCESS-TIMESTAMP": "ts",
        },
    ):
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            request.return_value.status_code = 200
            request.return_value.json = MagicMock(return_value={"order": {"order_id": "1"}})
            request.return_value.raise_for_status = MagicMock()
            await client._request(
                "POST",
                "/portfolio/orders",
                json={"ticker": "MARKET"},
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
    request.assert_awaited_once()
    assert "_capability" not in request.await_args.kwargs


@pytest.mark.asyncio
async def test_read_only_order_requests_remain_available_without_capability(client):
    with patch(
        "kalshi.client.sign_request",
        return_value={
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "sig",
            "KALSHI-ACCESS-TIMESTAMP": "ts",
        },
    ):
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            request.return_value.status_code = 200
            request.return_value.json = MagicMock(return_value={"orders": []})
            request.return_value.raise_for_status = MagicMock()
            result = await client.get_orders()
    assert result == {"orders": []}
    request.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_order_uses_same_explicit_capability_contract(client):
    with patch("kalshi.client.sign_request") as sign_request:
        with patch.object(client.client, "request", new_callable=AsyncMock) as request:
            with pytest.raises(
                PermissionError,
                match="DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL",
            ):
                await client.cancel_order("order-123")
    sign_request.assert_not_called()
    request.assert_not_awaited()

@pytest.mark.asyncio
async def test_rate_limiter_retries_connect_error(client):
    client.limiter.base_delay = 0
    with patch("kalshi.client.sign_request", return_value={"KALSHI-ACCESS-KEY": "test", "KALSHI-ACCESS-SIGNATURE": "sig", "KALSHI-ACCESS-TIMESTAMP": "ts"}) as _:
        with patch.object(client.client, "request", new_callable=AsyncMock) as m:
            m.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(httpx.ConnectError):
                await client.get_markets()
            assert m.call_count == client.limiter.max_retries + 1
