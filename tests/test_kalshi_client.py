import pytest
import os
import httpx
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock
from kalshi.client import KalshiClient, _CENTRAL_FIREWALL_SUBMIT_CAPABILITY
from kalshi.signer import sign_request
from kalshi.error_classifier import classify, KalshiErrorCategory


def _json_response(payload):
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://kalshi.invalid/test"),
    )


@pytest.fixture
def client():
    return KalshiClient()


def test_production_client_rejects_ambient_endpoint_redirect(monkeypatch):
    monkeypatch.setenv("KALSHI_API_BASE", "https://attacker.invalid")
    monkeypatch.setenv("KALSHI_API_VERSION", "trade-api/v999")

    with pytest.raises(RuntimeError, match="KALSHI_ENDPOINT_OVERRIDE_REJECTED"):
        KalshiClient()


def test_production_client_allows_only_exact_endpoint_pin(monkeypatch):
    monkeypatch.setenv(
        "KALSHI_API_BASE",
        "https://external-api.kalshi.com/",
    )
    monkeypatch.setenv("KALSHI_API_VERSION", "/trade-api/v2/")

    pinned = KalshiClient()
    assert str(pinned.client.base_url) == (
        "https://external-api.kalshi.com/trade-api/v2/"
    )


def test_production_client_disables_environment_proxy_trust(monkeypatch):
    monkeypatch.delenv("KALSHI_API_BASE", raising=False)
    monkeypatch.delenv("KALSHI_API_VERSION", raising=False)

    with patch("kalshi.client.httpx.AsyncClient") as async_client:
        KalshiClient()

    assert async_client.call_args.kwargs["trust_env"] is False


def test_signer_path_prefix_ignores_ambient_version_redirect(monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test-key")
    monkeypatch.setenv("KALSHI_API_VERSION", "trade-api/v999")
    private_key = MagicMock()
    private_key.sign.return_value = b"signature"

    with patch("kalshi.signer.load_private_key", return_value=private_key):
        sign_request("GET", "/markets")

    signed_message = private_key.sign.call_args.args[0].decode("utf-8")
    assert signed_message.endswith("GET/trade-api/v2/markets")
    assert "v999" not in signed_message


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
            m.return_value = _json_response(mock_resp)
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
            request.return_value = _json_response({"orderbook": {"bids": [{"price": 48, "count": 1}, {"price": 40, "count": 1}], "asks": [{"price": 60, "count": 1}, {"price": 52, "count": 1}]}})
            book = await client.get_orderbook("MARKET")
            assert [level.price for level in book.bids] == [40, 48]
            assert [level.price for level in book.asks] == [52, 60]

            request.return_value = _json_response({"orderbook": {}})
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
            m.return_value = _json_response({"status": "success"})
            permit = await client.prepare_order_mutation(
                "POST",
                "/portfolio/events/orders",
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
            await client.create_order(
                order,
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                _mutation_permit=permit,
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
        ("POST", "/portfolio/events/orders"),
        ("DELETE", "/portfolio/events/orders/order-123"),
        ("POST", "/portfolio/events/orders/order-123/amend"),
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
                    "/portfolio/events/orders",
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
            request.return_value = _json_response({"order": {"order_id": "1"}})
            permit = await client.prepare_order_mutation(
                "POST",
                "/portfolio/events/orders",
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
            await client._request(
                "POST",
                "/portfolio/events/orders",
                json={"ticker": "MARKET"},
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                _mutation_permit=permit,
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
            request.return_value = _json_response({"orders": []})
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("ambiguous connection failure"),
        httpx.ReadTimeout("ambiguous response timeout"),
    ],
)
async def test_order_mutation_transport_is_exactly_one_attempt(client, failure):
    client.limiter.base_delay = 0
    with patch(
        "kalshi.client.sign_request",
        return_value={
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "sig",
            "KALSHI-ACCESS-TIMESTAMP": "ts",
        },
    ):
        with patch.object(
            client.client,
            "request",
            new_callable=AsyncMock,
        ) as request:
            request.side_effect = failure
            permit = await client.prepare_order_mutation(
                "POST",
                "/portfolio/events/orders",
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
            with pytest.raises(type(failure)):
                await client.create_order(
                    {
                        "ticker": "MARKET",
                        "client_order_id": "proposal-1",
                    },
                    _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                    _mutation_permit=permit,
                )
    assert request.await_count == 1


@pytest.mark.asyncio
async def test_order_mutation_http_429_is_not_retried(client):
    response = httpx.Response(
        429,
        request=httpx.Request(
            "POST",
            "https://kalshi.invalid/portfolio/events/orders",
        ),
        json={"error": "rate limited"},
    )
    with patch(
        "kalshi.client.sign_request",
        return_value={
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "sig",
            "KALSHI-ACCESS-TIMESTAMP": "ts",
        },
    ):
        with patch.object(
            client.client,
            "request",
            new_callable=AsyncMock,
            return_value=response,
        ) as request:
            permit = await client.prepare_order_mutation(
                "POST",
                "/portfolio/events/orders",
                _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.create_order(
                    {
                        "ticker": "MARKET",
                        "client_order_id": "proposal-1",
                    },
                    _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                    _mutation_permit=permit,
                )
    assert request.await_count == 1
