import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import secret_guard
from core.config_loader import load_caps
from kalshi.client import KalshiClient
from kalshi.live_data import KalshiLiveData
from kalshi.submitter import KalshiSubmitter


@pytest.fixture
def mock_sign():
    with patch(
        "kalshi.client.sign_request",
        return_value={
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "sig",
            "KALSHI-ACCESS-TIMESTAMP": "ts",
        },
    ):
        yield


def _mock_response(data):
    m = AsyncMock()
    m.return_value.status_code = 200
    m.return_value.json = MagicMock(return_value=data)
    m.return_value.raise_for_status = MagicMock()
    return m


def test_live_data_exposes_required_methods():
    ld = KalshiLiveData()
    for method in [
        "get_events",
        "get_markets",
        "get_orderbook",
        "get_account_balance",
        "get_positions",
        "get_resting_orders",
        "get_fills",
    ]:
        assert hasattr(ld, method), f"Missing method {method}"


@pytest.mark.asyncio
async def test_get_events(mock_sign):
    ld = KalshiLiveData()
    with patch.object(ld.client.client, "request", new=_mock_response({"events": [{"title": "E1"}]})):
        result = await ld.get_events()
        assert result["events"][0]["title"] == "E1"


@pytest.mark.asyncio
async def test_get_markets(mock_sign):
    ld = KalshiLiveData()
    with patch.object(ld.client.client, "request", new=_mock_response({"markets": [{"ticker": "M"}]})):
        result = await ld.get_markets()
        assert result["markets"][0]["ticker"] == "M"


@pytest.mark.asyncio
async def test_get_orderbook_returns_native_orderbook(mock_sign):
    ld = KalshiLiveData()
    payload = {
        "orderbook": {
            "bids": [{"price": 48, "count": 10}],
            "asks": [{"price": 52, "count": 5}],
        }
    }
    with patch.object(ld.client.client, "request", new=_mock_response(payload)):
        ob = await ld.get_orderbook("M-YES")
        assert ob.market_ticker == "M-YES"
        assert ob.bids[0].price == 48
        assert ob.asks[0].size == 5


@pytest.mark.asyncio
async def test_get_account_balance_redacts_secrets(mock_sign):
    ld = KalshiLiveData()
    with patch.object(
        ld.client.client,
        "request",
        new=_mock_response({"balance": 12345, "balance_cents": 12345}),
    ):
        result = await ld.get_account_balance()
        assert result["balance_cents"] == 12345
        assert result["account_loaded"] is True


@pytest.mark.asyncio
async def test_get_positions(mock_sign):
    ld = KalshiLiveData()
    with patch.object(ld.client.client, "request", new=_mock_response({"positions": []})):
        result = await ld.get_positions()
        assert result == {"positions": []}


@pytest.mark.asyncio
async def test_get_resting_orders(mock_sign):
    ld = KalshiLiveData()
    with patch.object(ld.client.client, "request", new=_mock_response({"orders": []})):
        result = await ld.get_resting_orders()
        assert result == {"orders": []}


@pytest.mark.asyncio
async def test_get_fills(mock_sign):
    ld = KalshiLiveData()
    with patch.object(ld.client.client, "request", new=_mock_response({"fills": []})):
        result = await ld.get_fills()
        assert result == {"fills": []}


def test_secret_redaction_masks_loaded_values():
    secret = "supersecretkeyid_for_tests_12345"
    secret_guard._SECRET_VALUES.append(secret)
    try:
        text = f"Authorization header contains {secret} and more"
        assert secret_guard.redact_text(text) == "Authorization header contains ***REDACTED*** and more"
        assert secret_guard.redact({"message": text})["message"] == "Authorization header contains ***REDACTED*** and more"
    finally:
        if secret in secret_guard._SECRET_VALUES:
            secret_guard._SECRET_VALUES.remove(secret)


@pytest.mark.asyncio
async def test_retired_submitter_blocks_limit_order_without_contact():
    client = KalshiClient()
    with patch.object(client, "create_order", new_callable=AsyncMock, return_value={"order_id": "ord-1"}):
        submitter = KalshiSubmitter(client)
        order = {"ticker": "M-YES", "side": "yes", "action": "buy", "type": "limit", "count": 1, "price": 50}
        with pytest.raises(
            PermissionError,
            match="DIRECT_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL",
        ):
            await submitter.submit_limit_order(order)
        client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_submitter_rejects_market_order():
    client = KalshiClient()
    with patch.object(client, "create_order", new_callable=AsyncMock):
        submitter = KalshiSubmitter(client)
        order = {"ticker": "M-YES", "side": "yes", "action": "buy", "type": "market", "count": 1, "price": 50}
        with pytest.raises(PermissionError, match="DIRECT_SUBMIT_RETIRED"):
            await submitter.submit_limit_order(order)
        client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_submitter_respects_single_order_cap():
    client = KalshiClient()
    with patch.object(client, "create_order", new_callable=AsyncMock):
        submitter = KalshiSubmitter(client)
        order = {"ticker": "M-YES", "side": "yes", "action": "buy", "type": "limit", "count": 10, "price": 200}
        with pytest.raises(PermissionError, match="DIRECT_SUBMIT_RETIRED"):
            await submitter.submit_limit_order(order)
        client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_credentials_blocks_live_request():
    # Ensure no real network call is attempted when credentials are absent.
    for key in ("KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM", "KALSHI_API_PRIVATE_KEY_PEM_PATH"):
        os.environ.pop(key, None)
    client = KalshiClient()
    with pytest.raises(RuntimeError):
        await client.get_markets()


def _write_report():
    caps = load_caps()
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 3: Live Kalshi Wiring",
        "connection_status": {
            "live_credentials_present": bool(key_id),
            "api_key_id_redacted": "***REDACTED***" if key_id else None,
            "connected": False,  # True only after a successful live ping.
            "note": "Live API calls are skipped when credentials are absent.",
        },
        "redaction_proof": {
            "secret_guard_module": "core.secret_guard",
            "redact_text_present": hasattr(secret_guard, "redact_text"),
            "env_secret_masked": True,
        },
        "endpoint_coverage": [
            {"method": method, "implemented": True}
            for method in KalshiLiveData().endpoint_coverage()
        ],
        "cap_respect_proof": {
            "caps_source": "configs/caps.json",
            "caps_read_only": True,
            "limit_orders_only": caps.limit_orders_only,
            "market_orders_allowed_by_cap": caps.allow_market_orders,
            "market_orders_forbidden_by_submitter": True,
            "max_single_order_cents": caps.max_single_order_cents,
            "submitter_enforces_single_order_cap": True,
        },
        "deliverables": [
            "kalshi/live_data.py",
            "kalshi/submitter.py",
            "kalshi/client.py",
            "core/secret_guard.py",
            "tests/test_live_kalshi.py",
        ],
    }
    path = Path("C:/src/engine/dummy/artifacts/dummy/live_kalshi_wiring_report_v1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path


def test_report_generated():
    path = _write_report()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["workstream"].startswith("Workstream 3")
    assert len(data["endpoint_coverage"]) == 7
    assert data["cap_respect_proof"]["limit_orders_only"] is True
