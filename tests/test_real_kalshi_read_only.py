"""Tests for real Kalshi READ_ONLY ingestion wrapper."""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing


@pytest.fixture
def clear_kalshi_creds(monkeypatch):
    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    monkeypatch.delenv("KALSHI_API_PRIVATE_KEY_PEM", raising=False)
    monkeypatch.delenv("KALSHI_API_PRIVATE_KEY_PEM_PATH", raising=False)


@pytest.fixture
def mock_kalshi_client():
    client = AsyncMock()
    client.get_account.return_value = {
        "user_id": "u1",
        "email": "test@example.com",
        "balance": 10000,
        "available_balance": 9000,
    }
    client.get_events.return_value = {
        "events": [{"event_ticker": "EVT", "title": "Event", "category": "weather", "status": "active"}]
    }
    client.get_markets.return_value = {
        "markets": [{"ticker": "MKT", "title": "Market", "status": "active", "category": "weather"}]
    }
    client.get_orderbook.return_value = type("OB", (), {
        "market_ticker": "MKT",
        "contract_ticker": "MKT-YES",
        "bids": [type("L", (), {"price": 48, "size": 10})],
        "asks": [type("L", (), {"price": 52, "size": 10})],
        "timestamp": datetime.now(timezone.utc),
    })()
    client.get_positions.return_value = {"positions": []}
    client.get_orders.return_value = {"orders": []}
    client.get_fills.return_value = {"fills": []}
    return client


def test_missing_credentials_raise(clear_kalshi_creds):
    with pytest.raises(KalshiCredentialsMissing):
        KalshiRealReadOnly()


@pytest.mark.asyncio
async def test_get_account_status_tracks_endpoint(mock_kalshi_client, monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "dummy")
    reader = KalshiRealReadOnly(client=mock_kalshi_client)
    result = await reader.get_account_status()
    assert result["user_id"] == "u1"
    assert "GET /portfolio/balance" in reader.endpoints_called()
    assert not reader.order_creating_endpoints_called()


@pytest.mark.asyncio
async def test_get_balance_redacts(mock_kalshi_client, monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "dummy")
    reader = KalshiRealReadOnly(client=mock_kalshi_client)
    balance = await reader.get_balance()
    assert balance["balance_cents"] == 10000
    assert "GET /portfolio/balance" in reader.endpoints_called()


@pytest.mark.asyncio
async def test_get_full_snapshot_no_order_endpoints(mock_kalshi_client, monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "dummy")
    reader = KalshiRealReadOnly(client=mock_kalshi_client)
    snapshot = await reader.get_full_snapshot("MKT-YES")
    assert "account_status" in snapshot
    assert "markets" in snapshot
    assert "orderbook" in snapshot
    assert "positions" in snapshot
    assert "resting_orders" in snapshot
    assert "fills" in snapshot
    order_creating = reader.order_creating_endpoints_called()
    assert not order_creating, f"Order-creating endpoints called: {order_creating}"


@pytest.mark.asyncio
async def test_timeout_is_unavailable_real_source_not_mock(
    mock_kalshi_client, monkeypatch
):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "dummy")
    monkeypatch.setattr("kalshi.live_data.KALSHI_READ_ONLY_TIMEOUT_SECONDS", 0.001)

    async def slow_account():
        await asyncio.sleep(0.05)
        return {}

    mock_kalshi_client.get_account.side_effect = slow_account
    reader = KalshiRealReadOnly(client=mock_kalshi_client)
    snapshot = await reader.get_full_snapshot("MKT-YES")

    assert snapshot["source"] == "kalshi_real_read_only"
    assert snapshot["source"] != "mock"
    assert snapshot["data_status"] == "UNAVAILABLE"
    assert snapshot["complete"] is False
    assert snapshot["data_authority"] is False
    assert snapshot["timeout"] is True
    assert snapshot["order_creating_endpoints"] == []


@pytest.mark.asyncio
async def test_real_credentials_present_skip_if_missing(monkeypatch):
    """Live Kalshi read-only ping.

    Credentials come from the shell env or, failing that, the local .env via
    the whitelisted reader (test-scoped; nothing leaks into other tests).
    Skips only where credentials are genuinely absent (e.g. CI), rejected, or
    the network is unreachable.
    """
    if not os.environ.get("KALSHI_API_KEY_ID"):
        from core.env_loader import read_whitelisted_env

        dotenv = read_whitelisted_env()
        if not dotenv.get("KALSHI_API_KEY_ID"):
            pytest.skip("Kalshi credentials not present")
        for key, value in dotenv.items():
            monkeypatch.setenv(key, value)
    reader = KalshiRealReadOnly()
    try:
        snapshot = await reader.get_full_snapshot("KXBTCDEMO")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            pytest.skip("Kalshi credentials rejected by the server")
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        pytest.skip(f"Kalshi unreachable: {type(exc).__name__}")
    except ValueError as exc:
        if "orderbook" in str(exc).lower() and "missing" in str(exc).lower():
            pytest.skip("Kalshi demo ticker currently has no usable two-sided orderbook")
        raise
    assert "account_status" in snapshot
    assert not reader.order_creating_endpoints_called()
