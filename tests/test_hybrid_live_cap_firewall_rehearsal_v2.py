"""Tests for V2 hybrid live-capped firewall rehearsal with strategy governor."""

import os
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from core import state as state_module
from core.config_loader import load_caps
from core.ontology import (
    AccountMode,
    ComplianceVerdict,
    EdgeEstimate,
    LiveOrderResult,
    TradeProposal,
)
from execution.hybrid_path import HybridLiveCapRehearsalV2
from live_firewall.firewall import LiveBrokerFirewall


@pytest.fixture(autouse=True)
def reset_state():
    fresh = state_module.DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module

    firewall_module.STATE = fresh
    # Keep a dummy Kalshi API key ID so the live firewall secrets check passes,
    # but remove any PEM material so KalshiRealReadOnly raises CredentialsMissing
    # and falls back to deterministic mock market data.
    original_key = os.environ.get("KALSHI_API_KEY_ID")
    original_pem = os.environ.pop("KALSHI_API_PRIVATE_KEY_PEM", None)
    original_pem_path = os.environ.pop("KALSHI_API_PRIVATE_KEY_PEM_PATH", None)
    os.environ["KALSHI_API_KEY_ID"] = "test-key-id"
    try:
        yield
    finally:
        if original_key is None:
            os.environ.pop("KALSHI_API_KEY_ID", None)
        else:
            os.environ["KALSHI_API_KEY_ID"] = original_key
        if original_pem is not None:
            os.environ["KALSHI_API_PRIVATE_KEY_PEM"] = original_pem
        if original_pem_path is not None:
            os.environ["KALSHI_API_PRIVATE_KEY_PEM_PATH"] = original_pem_path


def _caps_with_market(market: str):
    caps = load_caps()
    caps.allowed_markets = [market]
    return caps


def _patch_caps(market: str):
    caps = _caps_with_market(market)
    return (
        patch("live_firewall.firewall.load_caps", return_value=caps),
        patch("execution.hybrid_path.load_caps", return_value=caps),
    )


@pytest.mark.asyncio
async def test_rehearsal_blocked_by_default():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "rehearsal"
    assert result["would_submit"] is False
    assert result["blocked_reason"] == "live_submit_disabled"
    assert result["live_submitted"] is False
    assert result["strategy_governor_decision"] == "APPROVE_FOR_FIREWALL_REHEARSAL"
    assert result["firewall_rehearsal"]["order"]["type"] == "limit"


@pytest.mark.asyncio
async def test_rehearsal_would_submit_when_enabled():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        with patch.object(
            LiveBrokerFirewall,
            "submit",
            new=AsyncMock(
                return_value=LiveOrderResult(
                    success=True, order_id="o1", proof_reference="p1"
                )
            ),
        ), patch.object(LiveBrokerFirewall, "_live_submit_enabled", return_value=True):
            rehearsal = HybridLiveCapRehearsalV2()
            result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["would_submit"] is True
    assert result["live_submitted"] is True
    assert result["status"] == "live_submitted"


@pytest.mark.asyncio
async def test_rehearsal_requires_autonomous_live_capped_mode():
    state_module.STATE.set_mode(AccountMode.READ_ONLY)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "mode"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_kill_switch():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.enable_kill_switch("test")
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "blocked"
    assert "kill" in (result.get("blocked_reason") or "").lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_emergency_stop():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.trigger_emergency_stop()
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "blocked"
    assert "emergency" in (result.get("blocked_reason") or "").lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_compliance_failure():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = _caps_with_market("SPX-ABOVE-5000")
    caps.blocked_categories = ["SPX-ABOVE-5000"]
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
        "execution.hybrid_path.load_caps", return_value=caps
    ):
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "no_trade"
    assert result["strategy_governor_decision"] == "NO_TRADE"
    assert "compliance" in result["reason"].lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_poor_liquidity_via_governor():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = _caps_with_market("MEME-STALE")
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
        "execution.hybrid_path.load_caps", return_value=caps
    ):
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("MEME-STALE", "MEME-STALE-YES")

    assert result["status"] == "no_trade"
    assert result["strategy_governor_decision"] == "NO_TRADE"
    assert "liquidity" in result["reason"].lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_missing_proof_reference():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        # Force a proposal with an empty strategy proof reference.
        rehearsal._derive_trade_decision = lambda *args, **kwargs: TradeProposal(
            id="bad",
            market_ticker="SPX-ABOVE-5000",
            contract_ticker="SPX-ABOVE-5000-YES",
            side="yes",
            price_cents=52,
            size=1,
            forecast_reference="forecast_1",
            edge_estimate=EdgeEstimate(
                expected_edge_bps=500, edge_after_fees_bps=450, confidence_score=Decimal("0.6")
            ),
            risk_estimate="low",
            confidence_estimate=Decimal("0.6"),
            expected_fill_behavior="limit",
            stop_condition="none",
            cancellation_condition="none",
            cap_impact={},
            compliance_verdict=ComplianceVerdict(
                passed=True, blocked_categories=[], reason=""
            ),
            proof_reference="",
        )
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "proof"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_limit_order_only():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["firewall_rehearsal"]["order"]["type"] == "limit"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_no_real_order_submitted_by_default():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("SPX-ABOVE-5000")
    with a, b:
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["live_submitted"] is False
    assert result["order_result"] is None
