import pytest
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from core import state as state_module
from core.state import DummyState, STATE
from core.ontology import AccountMode, LiveOrderRequest, OrderBook, OrderBookLevel, Forecast, EdgeEstimate, Position
from live_firewall.firewall import LiveBrokerFirewall, REJECTED_ADAPTERS, mark_adapter_rejected
from live_firewall.exposure_tracker import ExposureTracker


@pytest.fixture(autouse=True)
def reset_state():
    """Reset the global DummyState and firewall guards before every test."""
    fresh = DummyState()
    state_module.STATE = fresh
    # The firewall module imported STATE at load time, so update its reference too.
    import live_firewall.firewall as firewall_module
    firewall_module.STATE = fresh
    REJECTED_ADAPTERS.clear()
    yield


def _make_request(**overrides):
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
    return LiveOrderRequest(**defaults)


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
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        strategy_references=[],
        proof_reference="fp1",
    )


@pytest.mark.asyncio
async def test_off_mode_blocks_orders():
    state_module.STATE.set_mode(AccountMode.OFF)
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow and "Mode" in v.reason


@pytest.mark.asyncio
async def test_read_only_blocks_orders():
    state_module.STATE.set_mode(AccountMode.READ_ONLY)
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow


@pytest.mark.asyncio
async def test_kill_switch_blocks_orders():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.enable_kill_switch("test")
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow and "Kill switch" in v.reason


@pytest.mark.asyncio
async def test_emergency_stop_blocks_orders():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.trigger_emergency_stop()
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow and "Emergency" in v.reason


@pytest.mark.asyncio
async def test_missing_api_key_blocks():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ.pop("KALSHI_API_KEY_ID", None)
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow and "API key" in v.reason


@pytest.mark.asyncio
async def test_market_not_allowlisted():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
    assert not v.allow and "allowlisted" in v.reason


@pytest.mark.asyncio
async def test_oversized_order_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(price_cents=200, size=10), _make_book(), _make_forecast())
        assert not v.allow and "Single order cap" in v.reason


@pytest.mark.asyncio
async def test_low_edge_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    f = _make_forecast()
    f.expected_edge = Decimal("0.001")
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), f)
        assert not v.allow and "edge" in v.reason.lower()


@pytest.mark.asyncio
async def test_missing_proof_reference_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(strategy_proof_reference=""), _make_book(), _make_forecast())
        assert not v.allow and "proof" in v.reason.lower()


@pytest.mark.asyncio
async def test_all_gates_pass_allows():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
        assert v.allow


@pytest.mark.asyncio
async def test_submit_creates_order_and_tracks_exposure():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    exposure = ExposureTracker()
    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "ord-123"}}
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch.object(
        LiveBrokerFirewall, "_live_submit_enabled", return_value=True
    ):
        fw = LiveBrokerFirewall(client, exposure)
        result = await fw.submit(_make_request(), _make_book(), _make_forecast())
        assert result.success
        assert result.order_id == "ord-123"
        assert len(exposure.order_history) == 1
        assert exposure.open_order_count() == 1
        assert "MARKET" in exposure.positions
        assert exposure.positions["MARKET"].quantity == 1
        client.create_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_rejects_evaluated_order():
    state_module.STATE.set_mode(AccountMode.OFF)
    exposure = ExposureTracker()
    client = AsyncMock()
    fw = LiveBrokerFirewall(client, exposure)
    result = await fw.submit(_make_request(), _make_book(), _make_forecast())
    assert not result.success
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocked_category_compliance_gate():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["politics-elections-us"]
    caps.blocked_categories = ["politics-elections-us-YES"]
    req = _make_request(
        market_ticker="politics-elections-us",
        contract_ticker="politics-elections-us-YES",
    )
    book = OrderBook(
        market_ticker="politics-elections-us",
        contract_ticker="politics-elections-us-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(req, book, _make_forecast())
        assert not v.allow and v.rejected_by == "compliance"


@pytest.mark.asyncio
async def test_stale_data_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    book = _make_book()
    book.timestamp = datetime.now(timezone.utc) - timedelta(seconds=31)
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), book, _make_forecast())
        assert not v.allow and v.rejected_by == "stale_data"


@pytest.mark.asyncio
async def test_spread_too_wide_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    book = OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=60, size=10)],
        timestamp=datetime.now(timezone.utc),
    )
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), book, _make_forecast())
        assert not v.allow and v.rejected_by == "spread"


@pytest.mark.asyncio
async def test_liquidity_too_low_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    book = OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        bids=[OrderBookLevel(price=48, size=1)],
        asks=[OrderBookLevel(price=52, size=1)],
        timestamp=datetime.now(timezone.utc),
    )
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), book, _make_forecast())
        assert not v.allow and v.rejected_by == "liquidity"


@pytest.mark.asyncio
async def test_fees_remove_edge_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    f = _make_forecast()
    f.edge_after_fees = Decimal("0")
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), f)
        assert not v.allow and v.rejected_by == "edge"


@pytest.mark.asyncio
async def test_market_exposure_cap_exceeded():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    exposure = ExposureTracker()
    exposure.update_position(Position(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        side="yes",
        quantity=5,
        avg_price_cents=100,
        unrealized_pnl_cents=0,
    ))
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, exposure)
        v = await fw.evaluate(_make_request(price_cents=50, size=1), _make_book(), _make_forecast())
        assert not v.allow and v.rejected_by == "market_exposure_cap"


@pytest.mark.asyncio
async def test_total_exposure_cap_exceeded():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    exposure = ExposureTracker()
    exposure.update_position(Position(
        market_ticker="OTHER",
        contract_ticker="OTHER-YES",
        side="yes",
        quantity=10,
        avg_price_cents=100,
        unrealized_pnl_cents=0,
    ))
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, exposure)
        v = await fw.evaluate(_make_request(price_cents=50, size=1), _make_book(), _make_forecast())
        assert not v.allow and v.rejected_by == "total_exposure_cap"


@pytest.mark.asyncio
async def test_daily_loss_cap_exceeded():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    state_module.STATE.daily_loss_cents = caps.max_daily_loss_cents
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
        assert not v.allow and v.rejected_by == "daily_loss_cap"


@pytest.mark.asyncio
async def test_order_frequency_cap_exceeded():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    exposure = ExposureTracker()
    for _ in range(caps.max_orders_per_hour):
        exposure.record_order("MARKET", 1, 50)
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, exposure)
        v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
        assert not v.allow and v.rejected_by == "frequency_cap"


@pytest.mark.asyncio
async def test_settlement_risk_too_high_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    f = _make_forecast()
    f.settlement_risk_score = Decimal("0.9")
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), f)
        assert not v.allow and v.rejected_by == "settlement_risk"


@pytest.mark.asyncio
async def test_unknown_adapter_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(_make_request(adapter_name="rogue_adapter"), _make_book(), _make_forecast())
    assert not v.allow and v.rejected_by == "unknown_adapter"


@pytest.mark.asyncio
async def test_secret_redaction_failure_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    fw = LiveBrokerFirewall(None, ExposureTracker())
    v = await fw.evaluate(
        _make_request(forecast_proof_reference="api_key='supersecret123456789'"),
        _make_book(),
        _make_forecast(),
    )
    assert not v.allow and v.rejected_by == "secret_redaction"


@pytest.mark.asyncio
async def test_repo_bypass_adapter_rejected():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    mark_adapter_rejected("kalshi_live_firewall_adapter")
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        v = await fw.evaluate(_make_request(), _make_book(), _make_forecast())
        assert not v.allow and v.rejected_by == "repo_bypass"
