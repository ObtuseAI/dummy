"""Tests for AUTONOMOUS_LIVE_CAPPED firewall rehearsal."""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from core import state as state_module
from core.config_loader import load_caps
from core.ontology import AccountMode, FirewallVerdict, Forecast, LiveOrderRequest, OrderBook, OrderBookLevel
from live_firewall.firewall import LiveBrokerFirewall, RehearsalVerdict
from live_firewall.exposure_tracker import ExposureTracker
from forecasting.model_influence_attestation import build_model_influence_attestation


def _make_book(stale: bool = False):
    ts = datetime.now(timezone.utc) - timedelta(seconds=120 if stale else 0)
    return OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET",
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=ts,
    )


def _make_forecast():
    return Forecast(
        market_ticker="MARKET",
        contract_ticker="MARKET",
        event_title="Event",
        contract_title="Yes",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        probability_delta=Decimal("0.05"),
        confidence_score=Decimal("0.8"),
        uncertainty_band=(Decimal("0.5"), Decimal("0.6")),
        expected_edge=Decimal("0.05"),
        # The firewall independently applies its half-sigma haircut and the
        # current fee schedule. Keep this upstream claim no more optimistic
        # than the 0.5c result after the maker schedule's taker-fee fallback.
        edge_after_fees=Decimal("0.005"),
        freshness_score=Decimal("1.0"),
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=Decimal("0.1"),
        source_summary="test",
        model_summary="test",
        calibration_notes="test",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        strategy_references=["test"],
        proof_reference="forecast_1",
    )


def _make_request(*, forecast=None, **overrides):
    defaults = dict(
        proposal_id="p1",
        market_ticker="MARKET",
        contract_ticker="MARKET",
        side="yes",
        price_cents=50,
        size=1,
        strategy_proof_reference="sp1",
        forecast_proof_reference="forecast_1",
        adapter_name="kalshi_live_firewall_adapter",
    )
    defaults.update(overrides)
    if forecast is None:
        return LiveOrderRequest(**defaults)
    return LiveOrderRequest(
        **defaults,
        model_influence_attestation=build_model_influence_attestation(
            forecast,
            defaults,
        ),
    )


@pytest.fixture(autouse=True)
def reset_state():
    fresh = state_module.DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module
    firewall_module.STATE = fresh
    os.environ["KALSHI_API_KEY_ID"] = "test"


def _metadata_client():
    client = AsyncMock()
    client.get_market.return_value = {
        "market": {
            "ticker": "MARKET",
            "event_ticker": "EVENT",
            "status": "open",
            "close_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
    }
    client.get_event.return_value = {
        "event": {
            "event_ticker": "EVENT",
            "series_ticker": "SERIES",
            "category": "Sports",
        }
    }
    client.get_series.return_value = {
        "series": {"ticker": "SERIES", "category": "Sports", "tags": []}
    }
    return client


@pytest.mark.asyncio
async def test_rehearsal_blocks_by_default():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(_metadata_client(), ExposureTracker())
        forecast = _make_forecast()
        verdict = await fw.submit_rehearsal(
            _make_request(forecast=forecast),
            _make_book(),
            forecast,
        )
        assert isinstance(verdict, RehearsalVerdict)
        assert verdict.firewall_verdict.allow is True
        assert verdict.would_submit is False
        assert verdict.blocked_reason == "live_submit_disabled"
        assert verdict.order is not None
        assert verdict.order["type"] == "limit"


@pytest.mark.asyncio
async def test_rehearsal_would_submit_when_enabled():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(_metadata_client(), ExposureTracker())
        fw.live_authority_verdict = lambda: FirewallVerdict(
            allow=True, reason="test authority"
        )
        forecast = _make_forecast()
        verdict = await fw.submit_rehearsal(
            _make_request(forecast=forecast),
            _make_book(),
            forecast,
        )
        assert verdict.would_submit is True
        assert verdict.blocked_reason is None


@pytest.mark.asyncio
async def test_rehearsal_blocks_oversized_order():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    caps.max_single_order_cents = 10
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(_make_request(price_cents=50, size=1), _make_book(), _make_forecast())
        assert verdict.would_submit is False
        assert "cap" in (verdict.blocked_reason or "").lower()


@pytest.mark.asyncio
async def test_rehearsal_blocks_stale_data():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(_make_request(), _make_book(stale=True), _make_forecast())
        assert verdict.would_submit is False
        assert "stale" in (verdict.blocked_reason or "").lower()


@pytest.mark.asyncio
async def test_rehearsal_blocks_kill_switch():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.enable_kill_switch("test")
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(_make_request(), _make_book(), _make_forecast())
        assert verdict.would_submit is False
        assert "kill" in (verdict.blocked_reason or "").lower()


@pytest.mark.asyncio
async def test_rehearsal_blocks_emergency_stop():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.trigger_emergency_stop()
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(_make_request(), _make_book(), _make_forecast())
        assert verdict.would_submit is False
        assert "emergency" in (verdict.blocked_reason or "").lower()


@pytest.mark.asyncio
async def test_rehearsal_blocks_unknown_adapter():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(_make_request(adapter_name="unknown_adapter"), _make_book(), _make_forecast())
        assert verdict.would_submit is False
        assert "unknown" in (verdict.blocked_reason or "").lower()


@pytest.mark.asyncio
async def test_rehearsal_blocks_missing_proof():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.submit_rehearsal(
            _make_request(strategy_proof_reference="", forecast_proof_reference=""),
            _make_book(),
            _make_forecast(),
        )
        assert verdict.would_submit is False
        assert "proof" in (verdict.blocked_reason or "").lower()
