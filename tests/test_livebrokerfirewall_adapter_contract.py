"""Contract tests for the LiveBrokerFirewall adapter interface.

These tests verify that the generic protocol is well-defined and that the
concrete Kalshi adapter satisfies it. No real network is used.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx
import pytest

from predator_mesh.brokers.livebrokerfirewall_adapter import (
    AdapterHealth,
    LimitOrderRequest,
    LiveBrokerFirewallAdapter,
    OrderState,
    OrderStatusResult,
    SubmitResult,
)
from predator_mesh.brokers.kalshi_livebrokerfirewall_adapter import (
    KalshiLiveBrokerFirewallAdapter,
)
from predator_mesh.brokers.kalshi_errors import BrokerErrorCode


def _minimal_limit_order(**overrides: Any) -> LimitOrderRequest:
    defaults = {
        "venue": "KALSHI",
        "order_type": "LIMIT",
        "market_orders_allowed": False,
        "side": "yes",
        "action": "buy",
        "price": 50,
        "quantity": 1,
        "idempotency_key": "proof-1",
        "market_ticker": "KXBTC-26DEC25000-C",
        "proof_id": "proof-1",
        "proof_target": "FIRST_REAL_PILOT_PROOF",
    }
    defaults.update(overrides)
    return LimitOrderRequest(**defaults)


class DummyAdapter(LiveBrokerFirewallAdapter):
    """Minimal concrete adapter for protocol verification."""

    def validate_environment(self) -> AdapterHealth:
        return AdapterHealth(ready=True, ok=True)

    async def submit_limit_order(self, order: LimitOrderRequest) -> SubmitResult:
        return SubmitResult(submitted=True, order_id="dummy-1", state=OrderState.OPEN)

    async def get_order_status(self, order_id: str) -> OrderStatusResult:
        return OrderStatusResult(order_id=order_id, state=OrderState.OPEN)

    def redact_diagnostics(self) -> dict[str, Any]:
        return {"redacted": True}


# -----------------------------------------------------------------------------
# Protocol shape
# -----------------------------------------------------------------------------

def test_adapter_is_abstract_base():
    assert inspect.isabstract(LiveBrokerFirewallAdapter)


def test_adapter_requires_four_methods():
    required = {"validate_environment", "submit_limit_order", "get_order_status", "redact_diagnostics"}
    assert required <= set(LiveBrokerFirewallAdapter.__abstractmethods__)


def test_dummy_adapter_satisfies_protocol():
    adapter = DummyAdapter()
    health = adapter.validate_environment()
    assert isinstance(health, AdapterHealth)
    assert health.ok is True


# -----------------------------------------------------------------------------
# Kalshi adapter contract
# -----------------------------------------------------------------------------

def test_kalshi_adapter_is_instance_of_base():
    adapter = KalshiLiveBrokerFirewallAdapter()
    assert isinstance(adapter, LiveBrokerFirewallAdapter)


def test_kalshi_adapter_imports_without_credentials():
    """Instantiation must not crash when credentials are absent."""
    adapter = KalshiLiveBrokerFirewallAdapter()
    assert adapter is not None


def test_kalshi_validate_environment_returns_adapter_health():
    adapter = KalshiLiveBrokerFirewallAdapter()
    health = adapter.validate_environment()
    assert isinstance(health, AdapterHealth)
    assert health.ready is False  # no credentials in test env
    assert health.ok is False
    assert any("CREDENTIALS_ABSENT" in e for e in health.errors)


def test_kalshi_redact_diagnostics_has_no_secrets():
    adapter = KalshiLiveBrokerFirewallAdapter()
    diag = adapter.redact_diagnostics()
    text = str(diag).lower()
    assert "api_key" not in text or "present" in text
    assert "private_key" not in text or "present" in text
    assert "secret" not in text
    assert diag["venue"] == "KALSHI"


@pytest.mark.asyncio
async def test_kalshi_rejects_market_order_before_transport():
    adapter = KalshiLiveBrokerFirewallAdapter()
    order = _minimal_limit_order(order_type="MARKET")
    result = await adapter.submit_limit_order(order)
    assert isinstance(result, SubmitResult)
    assert result.submitted is False
    assert result.state == OrderState.REJECTED
    assert any("MARKET_ORDER_REJECTED" in e for e in result.errors)


@pytest.mark.asyncio
async def test_kalshi_rejects_missing_idempotency_key():
    adapter = KalshiLiveBrokerFirewallAdapter()
    order = _minimal_limit_order(idempotency_key="")
    result = await adapter.submit_limit_order(order)
    assert result.submitted is False
    assert any("IDEMPOTENCY_KEY_MISSING" in e for e in result.errors)


@pytest.mark.asyncio
async def test_kalshi_rejects_cap_violation():
    adapter = KalshiLiveBrokerFirewallAdapter()
    order = _minimal_limit_order(price=99, quantity=2)  # 198 cents > 100 cap
    result = await adapter.submit_limit_order(order)
    assert result.submitted is False
    assert any("ORDER_SIZE_CAP_EXCEEDED" in e for e in result.errors)


@pytest.fixture
def fake_kalshi_credentials(monkeypatch):
    """Provide syntactically valid but fake Kalshi credentials for mocked tests."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("KALSHI_API_KEY_ID", "fake-key-id")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", pem)


@pytest.mark.asyncio
async def test_kalshi_legacy_submit_is_retired_without_transport(monkeypatch, fake_kalshi_credentials):
    """A valid legacy request cannot reach even a mocked transport."""
    captured: dict[str, Any] = {}

    async def fake_create_order(payload: dict[str, Any]) -> dict[str, Any]:
        captured["payload"] = payload
        return {"order_id": "ord-123", "status": "resting"}

    adapter = KalshiLiveBrokerFirewallAdapter(
        live_submit_enabled=True,
        caps_confirmed=True,
        command_seal_ready=True,
        resolver_armable=True,
        require_proof_lock=False,
        httpx_client=httpx.AsyncClient(),
    )
    monkeypatch.setattr(adapter._kalshi, "create_order", fake_create_order)

    order = _minimal_limit_order()
    result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.order_id is None
    assert result.state == OrderState.REJECTED
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert captured == {}


@pytest.mark.asyncio
async def test_kalshi_get_order_status_maps_unknown():
    adapter = KalshiLiveBrokerFirewallAdapter()
    result = await adapter.get_order_status("")
    assert isinstance(result, OrderStatusResult)
    assert result.state == OrderState.UNKNOWN


@pytest.mark.asyncio
async def test_kalshi_get_order_status_maps_filled(monkeypatch, fake_kalshi_credentials):
    async def fake_request(method: str, path: str) -> dict[str, Any]:
        return {"order_id": "ord-123", "status": "filled"}

    adapter = KalshiLiveBrokerFirewallAdapter(httpx_client=httpx.AsyncClient())
    monkeypatch.setattr(adapter._kalshi, "_request", fake_request)

    result = await adapter.get_order_status("ord-123")
    assert result.state == OrderState.FILLED
