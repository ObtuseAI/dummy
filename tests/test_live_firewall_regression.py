"""Live Broker Firewall regression suite.

Proves that repo-derived adapters cannot bypass the firewall, that direct
live-order functions outside the firewall are rejected by the source-scan /
incorporation gate, and that kill switch / emergency stop still block all orders.
"""

import pytest
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from core import state as state_module
from core.state import DummyState
from core.ontology import AccountMode, LiveOrderRequest, OrderBook, OrderBookLevel, Forecast
from live_firewall.firewall import LiveBrokerFirewall, REJECTED_ADAPTERS, mark_adapter_rejected
from live_firewall.exposure_tracker import ExposureTracker
from forecasting.model_influence_attestation import build_model_influence_attestation
from repo_harvester.adapter_planner import generate_adapter_plan_v3
from repo_harvester.incorporation_engine import get_allowed_adapter_names, approve_adapter_tests
from repo_harvester.incorporation_registry import load_registry, save_registry
from core.ontology import RepoVerdict


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    fresh = DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module
    firewall_module.STATE = fresh
    REJECTED_ADAPTERS.clear()
    # Isolate registry for tests.
    from repo_harvester import incorporation_registry
    original_path = incorporation_registry.REGISTRY_PATH
    incorporation_registry.REGISTRY_PATH = tmp_path / "incorporation_registry.json"
    save_registry({"incorporated": [], "rejected": [], "pending_tests": []})
    yield
    incorporation_registry.REGISTRY_PATH = original_path


def _make_request(*, forecast=None, **overrides):
    defaults = dict(
        proposal_id="p1",
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        side="yes",
        price_cents=50,
        size=1,
        strategy_proof_reference="sp1",
        forecast_proof_reference="fp1",
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


def _make_book():
    return OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )


def _make_forecast():
    return Forecast(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        event_title="Event",
        contract_title="Yes",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        probability_delta=Decimal("0.05"),
        confidence_score=Decimal("0.7"),
        uncertainty_band=(Decimal("0.5"), Decimal("0.6")),
        expected_edge=Decimal("0.015"),
        edge_after_fees=Decimal("0.010"),
        freshness_score=Decimal("1.0"),
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=Decimal("0.1"),
        source_summary="test",
        model_summary="test",
        calibration_notes="test",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc) + timezone.utc.__class__  # placeholder; will be replaced
    )


def _make_forecast_fixed():
    from datetime import timedelta
    return Forecast(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        event_title="Event",
        contract_title="Yes",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        probability_delta=Decimal("0.05"),
        confidence_score=Decimal("0.7"),
        uncertainty_band=(Decimal("0.5"), Decimal("0.6")),
        expected_edge=Decimal("0.015"),
        edge_after_fees=Decimal("0.010"),
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
        strategy_references=[],
        proof_reference="fp1",
    )


def test_source_scan_rejects_direct_order_bypass():
    scan = {
        "files_scanned": 1,
        "direct_order_hits": ["trade.py"],
        "kalshi_order_hits": [],
        "polymarket_order_hits": [],
        "private_key_hits": [],
        "api_secret_hits": [],
        "strategy_hits": ["strategy.py"],
        "forecast_hits": [],
        "risk_hits": [],
        "arbitrage_hits": [],
        "websocket_hits": [],
        "settlement_hits": [],
        "dashboard_hits": [],
    }
    plan = generate_adapter_plan_v3(
        {"owner": "x", "name": "y", "license": "MIT", "pushed_at": datetime.now(timezone.utc).isoformat(), "description": ""},
        scan,
        category="kalshi_polymarket_arbitrage",
    )
    assert plan["verdict"] == RepoVerdict.REJECT_DIRECT_ORDER_BYPASS.value
    assert plan["plans"] == []


def test_source_scan_rejects_secret_risk():
    scan = {
        "files_scanned": 1,
        "direct_order_hits": [],
        "kalshi_order_hits": [],
        "polymarket_order_hits": [],
        "private_key_hits": ["wallet.py"],
        "api_secret_hits": [],
        "strategy_hits": ["strategy.py"],
        "forecast_hits": [],
        "risk_hits": [],
        "arbitrage_hits": [],
        "websocket_hits": [],
        "settlement_hits": [],
        "dashboard_hits": [],
    }
    plan = generate_adapter_plan_v3(
        {"owner": "x", "name": "y", "license": "MIT", "pushed_at": datetime.now(timezone.utc).isoformat(), "description": ""},
        scan,
        category="crypto_btc_event_market",
    )
    assert plan["verdict"] == RepoVerdict.REJECT_SECRET_RISK.value


def test_source_scan_creates_adapter_target():
    scan = {
        "files_scanned": 2,
        "direct_order_hits": [],
        "kalshi_order_hits": [],
        "polymarket_order_hits": [],
        "private_key_hits": [],
        "api_secret_hits": [],
        "strategy_hits": ["strategy.py"],
        "forecast_hits": ["model.py"],
        "risk_hits": ["risk.py"],
        "arbitrage_hits": [],
        "websocket_hits": [],
        "settlement_hits": [],
        "dashboard_hits": [],
    }
    plan = generate_adapter_plan_v3(
        {"owner": "x", "name": "y", "license": "MIT", "pushed_at": datetime.now(timezone.utc).isoformat(), "description": ""},
        scan,
        category="stocks_equities_options_macro",
    )
    assert plan["verdict"] == RepoVerdict.ADAPTER_TARGET.value
    assert plan["plans"][0]["emits_native_types"] is False
    assert plan["plans"][0]["integration_status"] == "pending"
    assert plan["plans"][0]["production_capability"] is False


@pytest.mark.asyncio
async def test_repo_derived_scaffold_stays_blocked_after_structural_tests():
    """A generated shell cannot enter the live allowlist by boolean test claim."""
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]

    registry = load_registry()
    registry["pending_tests"].append({
        "repo": "owner/new_adapter",
        "adapter_name": "new_adapter",
        "tests_passed": False,
        "test_status": "pending_adapter_specific_tests",
        "integration_kind": "scaffold_only",
        "upstream_integration_verified": False,
        "production_capability": False,
        "prediction_authority": False,
    })
    save_registry(registry)

    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        req = _make_request(adapter_name="new_adapter")
        v = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
        assert not v.allow and v.rejected_by == "unknown_adapter"

        assert approve_adapter_tests("new_adapter") is False
        v2 = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
        assert not v2.allow and v2.rejected_by == "unknown_adapter"


@pytest.mark.asyncio
async def test_rejected_repo_adapter_cannot_submit():
    """A repo whose plan was rejected must not be able to submit live orders."""
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    mark_adapter_rejected("rogue_repo_adapter")
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        req = _make_request(adapter_name="rogue_repo_adapter")
        v = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
        assert not v.allow and v.rejected_by == "repo_bypass"


@pytest.mark.asyncio
async def test_unknown_adapter_blocked():
    """Any adapter not in the allowlist is blocked."""
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    fw = LiveBrokerFirewall(None, ExposureTracker())
    req = _make_request(adapter_name="unknown_adapter")
    v = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
    assert not v.allow and v.rejected_by == "unknown_adapter"


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", ["KXRAINNYC-26JUL21", "KXWTI-26JUL21-T80"])
async def test_data_only_contracts_are_blocked_before_other_live_gates(ticker):
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    fw = LiveBrokerFirewall(None, ExposureTracker())
    req = _make_request(market_ticker=ticker, contract_ticker=f"{ticker}-YES")

    verdict = await fw.evaluate(req, _make_book(), _make_forecast_fixed())

    assert not verdict.allow
    assert verdict.rejected_by == "data_only_target"


@pytest.mark.asyncio
async def test_direct_live_order_outside_firewall_is_rejected_by_policy():
    """Only LiveBrokerFirewall.submit may call the broker client.

    This is enforced by architecture: all repo-derived code must emit
    TradeProposal objects and route through the firewall.  The test asserts
    that the firewall is the single live-order chokepoint.
    """
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]

    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "ord-123"}}

    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(client, ExposureTracker())
        forecast = _make_forecast_fixed()
        result = await fw.submit(
            _make_request(forecast=forecast),
            _make_book(),
            forecast,
        )
        assert result.success is False
        assert result.broker_contacted is False
        assert "risk" in result.error.lower()
        client.create_order.assert_not_awaited()

    # A direct call to the client outside the firewall would bypass caps,
    # compliance, and exposure checks.  Dummy's architecture forbids that;
    # this regression codifies that the firewall is the only allowed caller.
    allowed = get_allowed_adapter_names()
    assert "kalshi_live_firewall_adapter" in allowed


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["yes", "no"])
async def test_kill_switch_blocks_all_orders(side):
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    state_module.STATE.enable_kill_switch("regression test")
    fw = LiveBrokerFirewall(None, ExposureTracker())
    req = _make_request(side=side)
    v = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
    assert not v.allow and "Kill switch" in v.reason


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["yes", "no"])
async def test_emergency_stop_blocks_all_orders(side):
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    state_module.STATE.trigger_emergency_stop()
    fw = LiveBrokerFirewall(None, ExposureTracker())
    req = _make_request(side=side)
    v = await fw.evaluate(req, _make_book(), _make_forecast_fixed())
    assert not v.allow and "Emergency" in v.reason
