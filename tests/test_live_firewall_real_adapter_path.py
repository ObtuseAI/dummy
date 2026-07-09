"""Tests for LiveBrokerFirewall.submit_limit_order_adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from live_firewall.firewall import LiveBrokerFirewall
from live_firewall.exposure_tracker import ExposureTracker
from predator_mesh.brokers import LimitOrderRequest, OrderState, SubmitResult


def _base_request(**overrides: Any) -> LimitOrderRequest:
    defaults: dict[str, Any] = {
        "venue": "KALSHI",
        "order_type": "LIMIT",
        "market_orders_allowed": False,
        "side": "yes",
        "action": "buy",
        "price": 1,
        "quantity": 1,
        "idempotency_key": "idem-001",
        "market_ticker": "TEST-01",
        "proof_id": "proof-001",
        "proof_target": "FIRST_REAL_PILOT_PROOF",
        "client_order_id": "idem-001",
        "max_order_count": 1,
        "max_order_size_cents": 100,
    }
    defaults.update(overrides)
    return LimitOrderRequest(**defaults)


def _firewall() -> LiveBrokerFirewall:
    return LiveBrokerFirewall(kalshi_client=None, exposure_tracker=ExposureTracker())


@pytest.mark.asyncio
async def test_blocks_when_live_submit_disabled(monkeypatch):
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: {"enabled": False})
    fw = _firewall()
    result = await fw.submit_limit_order_adapter(_base_request())
    assert result.success is False
    assert result.error == "live_submit_disabled"


@pytest.mark.asyncio
async def test_blocks_when_env_gate_missing(monkeypatch):
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("live_firewall.firewall._command_seal_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._caps_strict", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._descriptor_staged", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._kalshi_credentials_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._proof_lock_clear", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "0")
    fw = _firewall()
    result = await fw.submit_limit_order_adapter(_base_request())
    assert result.success is False
    assert result.error == "ENV_GATE_MISSING"


@pytest.mark.asyncio
async def test_blocks_market_order(monkeypatch):
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("live_firewall.firewall._command_seal_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._caps_strict", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._descriptor_staged", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._kalshi_credentials_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._proof_lock_clear", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")
    fw = _firewall()
    result = await fw.submit_limit_order_adapter(_base_request(order_type="MARKET"))
    assert result.success is False
    assert result.error == "MARKET_ORDER_REJECTED"


@pytest.mark.asyncio
async def test_blocks_max_order_count_above_one(monkeypatch):
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("live_firewall.firewall._command_seal_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._caps_strict", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._descriptor_staged", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._kalshi_credentials_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._proof_lock_clear", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")
    fw = _firewall()
    result = await fw.submit_limit_order_adapter(_base_request(max_order_count=2))
    assert result.success is False
    assert result.error == "MAX_ORDER_COUNT_EXCEEDED"


@pytest.mark.asyncio
async def test_calls_adapter_and_returns_success(monkeypatch):
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("live_firewall.firewall._command_seal_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._caps_strict", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._descriptor_staged", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._kalshi_credentials_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._proof_lock_clear", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")

    fake_adapter = AsyncMock()
    fake_adapter.submit_limit_order = AsyncMock(
        return_value=SubmitResult(
            submitted=True, order_id="ord-123", state=OrderState.OPEN, raw={}
        )
    )
    fake_adapter.close = AsyncMock()

    with patch("predator_mesh.brokers.kalshi_livebrokerfirewall_adapter.KalshiLiveBrokerFirewallAdapter", return_value=fake_adapter):
        fw = _firewall()
        result = await fw.submit_limit_order_adapter(_base_request())

    assert result.success is True
    assert result.order_id == "ord-123"
    fake_adapter.submit_limit_order.assert_awaited_once()
    fake_adapter.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_broker_rejection_returns_failure(monkeypatch):
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("live_firewall.firewall._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("live_firewall.firewall._command_seal_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._caps_strict", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._descriptor_staged", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._kalshi_credentials_ready", lambda: True)
    monkeypatch.setattr("live_firewall.firewall._proof_lock_clear", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")

    fake_adapter = AsyncMock()
    fake_adapter.submit_limit_order = AsyncMock(
        return_value=SubmitResult(
            submitted=False, order_id=None, state=OrderState.REJECTED, raw={"status_code": 400}, errors=["BROKER_REJECTED"]
        )
    )
    fake_adapter.close = AsyncMock()

    with patch("predator_mesh.brokers.kalshi_livebrokerfirewall_adapter.KalshiLiveBrokerFirewallAdapter", return_value=fake_adapter):
        fw = _firewall()
        result = await fw.submit_limit_order_adapter(_base_request())

    assert result.success is False
    assert result.error == "BROKER_REJECTED"
    assert result.broker_rejection_code == "BROKER_REJECTED"
    assert result.broker_rejection_http_status == 400
    assert result.broker_rejection_raw_redacted == {"status_code": 400}
