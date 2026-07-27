"""Tests for the real Kalshi LiveBrokerFirewall adapter.

All broker interaction is mocked with httpx.MockTransport; no test hits the
real Kalshi API. Credential material is generated in-memory and never logged.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import kalshi.signer
from predator_mesh.brokers import (
    BrokerErrorCode,
    KalshiLiveBrokerFirewallAdapter,
    LimitOrderRequest,
    OrderState,
)


def _generate_rsa_pem() -> str:
    key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture
def rsa_private_key_pem() -> str:
    return _generate_rsa_pem()


@pytest.fixture
def kalshi_env(monkeypatch, rsa_private_key_pem: str) -> dict[str, str]:
    """Provide valid Kalshi credential env vars and clean legacy aliases."""
    env: dict[str, str] = {
        "KALSHI_API_KEY_ID": "test-key-id",
        "KALSHI_API_PRIVATE_KEY_PEM": rsa_private_key_pem,
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    for legacy in (
        "KALSHI_PRIVATE_KEY",
        "KALSHI_PRIVATE_KEY_PATH",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(legacy, raising=False)
    return env


@pytest.fixture
def no_kalshi_env(monkeypatch) -> None:
    """Remove all Kalshi credential env vars."""
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def _base_url() -> str:
    """Return a host-only base URL so mocked paths stay /portfolio/orders."""
    return kalshi.signer.BASE.rstrip("/")


def _make_transport(
    responses: dict[tuple[str, str], tuple[int, dict[str, Any]]],
    requests: list[dict[str, Any]],
) -> httpx.MockTransport:
    """Return a MockTransport that records requests and serves responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method.upper()
        requests.append({"method": method, "path": path, "headers": dict(request.headers)})
        key = (method, path)
        status, body = responses.get(key, (404, {"error": "not found"}))
        return httpx.Response(status_code=status, json=body)

    return httpx.MockTransport(handler)


def _base_order(**overrides: Any) -> LimitOrderRequest:
    defaults: dict[str, Any] = {
        "venue": "KALSHI",
        "order_type": "LIMIT",
        "market_orders_allowed": False,
        "side": "yes",
        "action": "buy",
        "price": 50,
        "quantity": 1,
        "idempotency_key": "test-idem-001",
        "market_ticker": "TEST-01",
        "proof_id": "proof-001",
        "proof_target": "target-001",
    }
    defaults.update(overrides)
    return LimitOrderRequest(**defaults)


def _armed_adapter(httpx_client: httpx.AsyncClient) -> KalshiLiveBrokerFirewallAdapter:
    return KalshiLiveBrokerFirewallAdapter(
        live_submit_enabled=True,
        caps_confirmed=True,
        kill_switch_active=False,
        command_seal_ready=True,
        resolver_armable=True,
        httpx_client=httpx_client,
    )


# ---------------------------------------------------------------------------
# Import / construction without credentials
# ---------------------------------------------------------------------------


def test_imports_without_credentials(no_kalshi_env) -> None:
    """The package imports cleanly even when no credentials are configured."""
    adapter = KalshiLiveBrokerFirewallAdapter()
    assert adapter is not None


async def test_validate_environment_not_ready_without_credentials(no_kalshi_env) -> None:
    adapter = KalshiLiveBrokerFirewallAdapter()
    health = adapter.validate_environment()
    assert health.ready is False
    assert BrokerErrorCode.CREDENTIALS_ABSENT in health.errors
    # Diagnostics contain no secret material.
    diag = health.diagnostics
    assert diag["key_id_present"] is False
    assert diag["key_loaded"] is False


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------


async def test_credentials_redacted_in_diagnostics(kalshi_env) -> None:
    adapter = KalshiLiveBrokerFirewallAdapter()
    diag = adapter.redact_diagnostics()
    assert diag["key_id_present"] is True
    assert diag["key_loaded"] is True
    # The actual key id and PEM must not appear anywhere in diagnostics.
    diag_text = str(diag)
    assert kalshi_env["KALSHI_API_KEY_ID"] not in diag_text
    assert kalshi_env["KALSHI_API_PRIVATE_KEY_PEM"] not in diag_text
    assert "BEGIN RSA PRIVATE KEY" not in diag_text
    assert "BEGIN PRIVATE KEY" not in diag_text


async def test_retired_submit_path_returns_no_secrets_or_transport(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    responses = {
        ("POST", "/portfolio/orders"): (
            200,
            {"order_id": "ord-123", "status": "resting"},
        )
    }
    transport = _make_transport(responses, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order()
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.order_id is None
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert requests == []
    # Raw broker response should contain order fields, not headers/signatures.
    raw_text = str(result.raw)
    assert kalshi_env["KALSHI_API_KEY_ID"] not in raw_text
    assert kalshi_env["KALSHI_API_PRIVATE_KEY_PEM"] not in raw_text
    assert "signature" not in raw_text.lower()
    assert "KALSHI-ACCESS-SIGNATURE" not in raw_text


# ---------------------------------------------------------------------------
# Pre-broker rejections
# ---------------------------------------------------------------------------


async def test_market_order_rejected_before_transport_call(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    transport = _make_transport({}, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order(order_type="MARKET")
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.state == OrderState.REJECTED
    assert BrokerErrorCode.MARKET_ORDER_REJECTED in result.errors
    assert len(requests) == 0


async def test_market_orders_allowed_flag_rejected(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    transport = _make_transport({}, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order(market_orders_allowed=True)
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert BrokerErrorCode.MARKET_ORDERS_NOT_ALLOWED in result.errors
    assert len(requests) == 0


async def test_missing_idempotency_key_rejected(kalshi_env) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order(idempotency_key="")
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert BrokerErrorCode.IDEMPOTENCY_KEY_MISSING in result.errors


async def test_cap_violations_rejected(kalshi_env) -> None:
    adapter = KalshiLiveBrokerFirewallAdapter(
        live_submit_enabled=True,
        caps_confirmed=True,
        kill_switch_active=False,
        command_seal_ready=True,
        resolver_armable=True,
        httpx_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
            base_url=_base_url(),
        ),
    )

    cases = [
        _base_order(price=0, quantity=1),
        _base_order(price=100, quantity=1),
        _base_order(price=50, quantity=0),
        _base_order(price=50, quantity=10),  # notional 500 > 100
        _base_order(max_order_count=2),
    ]

    for order in cases:
        result = await adapter.submit_limit_order(order)
        assert result.submitted is False, order
        assert result.errors, order

    await adapter.close()


async def test_incomplete_proof_lock_rejected(kalshi_env) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order(proof_target=None)
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert BrokerErrorCode.PROOF_LOCK_INCOMPLETE in result.errors


# ---------------------------------------------------------------------------
# Successful mocked submission
# ---------------------------------------------------------------------------


async def test_valid_limit_order_is_blocked_by_retired_adapter(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    responses = {
        ("POST", "/portfolio/orders"): (
            200,
            {"order_id": "ord-abc", "status": "resting"},
        )
    }
    transport = _make_transport(responses, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order()
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.order_id is None
    assert result.state == OrderState.REJECTED
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert requests == []


async def test_retired_adapter_never_normalizes_fake_submit(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    responses = {
        ("POST", "/portfolio/orders"): (
            200,
            {"order_id": "ord-norm", "status": "filled"},
        )
    }
    transport = _make_transport(responses, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order()
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.order_id is None
    assert result.state == OrderState.REJECTED
    assert result.raw == {}
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert requests == []


async def test_retired_adapter_does_not_contact_mocked_reject_transport(kalshi_env) -> None:
    requests: list[dict[str, Any]] = []
    responses = {
        ("POST", "/portfolio/orders"): (
            400,
            {"error": "price out of bounds"},
        )
    }
    transport = _make_transport(responses, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        order = _base_order()
        result = await adapter.submit_limit_order(order)

    assert result.submitted is False
    assert result.state == OrderState.REJECTED
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert result.raw == {}
    assert requests == []


# ---------------------------------------------------------------------------
# Order status normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kalshi_status, expected_state",
    [
        ("filled", OrderState.FILLED),
        ("rejected", OrderState.REJECTED),
        ("canceled", OrderState.CANCELED),
        ("cancelled", OrderState.CANCELED),
        ("expired", OrderState.EXPIRED),
        ("partial_fill", OrderState.PARTIAL_FILL),
        ("resting", OrderState.OPEN),
        ("open", OrderState.OPEN),
        ("unknown_status", OrderState.UNKNOWN),
    ],
)
async def test_get_order_status_maps_states(
    kalshi_env, kalshi_status: str, expected_state: str
) -> None:
    order_id = "ord-status-1"
    requests: list[dict[str, Any]] = []
    responses = {
        ("GET", f"/portfolio/orders/{order_id}"): (
            200,
            {"order_id": order_id, "status": kalshi_status},
        )
    }
    transport = _make_transport(responses, requests)
    async with httpx.AsyncClient(transport=transport, base_url=_base_url()) as client:
        adapter = _armed_adapter(client)
        result = await adapter.get_order_status(order_id)

    assert result.order_id == order_id
    assert result.state == expected_state
    assert len(requests) == 1


# ---------------------------------------------------------------------------
# No real network
# ---------------------------------------------------------------------------


async def test_retired_submit_path_uses_no_network(kalshi_env) -> None:
    """Confirm that an injected transport is the only transport used."""
    requests: list[dict[str, Any]] = []
    responses = {
        ("POST", "/portfolio/orders"): (
            200,
            {"order_id": "net-check", "status": "resting"},
        )
    }
    transport = _make_transport(responses, requests)
    # Deliberately use a non-real base URL to prove we are not hitting Kalshi.
    async with httpx.AsyncClient(
        transport=transport, base_url="http://dummy-test.invalid"
    ) as client:
        adapter = _armed_adapter(client)
        result = await adapter.submit_limit_order(_base_order())

    assert result.submitted is False
    assert result.order_id is None
    assert result.errors == [BrokerErrorCode.LEGACY_SUBMIT_PATH_RETIRED]
    assert requests == []


# ---------------------------------------------------------------------------
# Legacy credential fallback
# ---------------------------------------------------------------------------


async def test_legacy_private_key_env_fallback(monkeypatch, rsa_private_key_pem: str) -> None:
    """The adapter can load a private key supplied via the legacy env name."""
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KALSHI_API_KEY_ID", "legacy-key")
    monkeypatch.setenv("KALSHI_PRIVATE_KEY", rsa_private_key_pem)

    adapter = KalshiLiveBrokerFirewallAdapter()
    assert adapter.validate_environment().ready is True
