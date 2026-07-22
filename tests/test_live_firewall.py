import pytest
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from core import state as state_module
from core.config_loader import load_caps
from core.state import DummyState
from core.ontology import AccountMode, LiveOrderRequest, OrderBook, OrderBookLevel, Forecast, Position
from live_firewall.firewall import LiveBrokerFirewall, REJECTED_ADAPTERS, mark_adapter_rejected
from live_firewall.exposure_tracker import ExposureTracker
from forecasting.model_influence_attestation import build_model_influence_attestation


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
    REJECTED_ADAPTERS.clear()


def _make_request(*, forecast=None, **overrides):
    defaults = dict(
        proposal_id="p1",
        market_ticker="MARKET",
        contract_ticker="MARKET",
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
        contract_ticker="MARKET",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
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
async def test_equity_index_prefix_blocks_at_firewall_preflight():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    fw = LiveBrokerFirewall(None, ExposureTracker())
    ticker = "KXINXY-26JUL22-B6400"
    request = _make_request(market_ticker=ticker, contract_ticker=ticker)
    book = _make_book().model_copy(
        update={"market_ticker": ticker, "contract_ticker": ticker}
    )
    forecast = _make_forecast().model_copy(
        update={"market_ticker": ticker, "contract_ticker": ticker}
    )

    verdict = await fw.evaluate(request, book, forecast)

    assert verdict.allow is False
    assert verdict.rejected_by == "equity_index_target_quarantine"


@pytest.mark.parametrize(
    "ticker",
    [
        "KXTSLA-26JUL22-B350",
        "KXBAA-28JANDELIV-700",
        "KXEBAYA-28JANGMV-92000000000.0",
        "KXCVNAA-28JANUNITS-910000",
        "KXFA-28JANUSSALES-2300000.0",
        "KXUALA-28JANPAX-190000000",
    ],
)
@pytest.mark.asyncio
async def test_equity_index_sink_gate_survives_replaced_evaluate(ticker):
    client = AsyncMock()
    fw = LiveBrokerFirewall(client, ExposureTracker())
    fw.evaluate = AsyncMock()

    result = await fw.submit(
        _make_request(market_ticker=ticker, contract_ticker=ticker),
        None,
        None,
    )

    assert result.success is False
    assert result.error == "prediction_target_quarantine"
    assert result.broker_contacted is False
    fw.evaluate.assert_not_awaited()
    client.create_order.assert_not_awaited()


def _verified_market_client(*, category, tags):
    client = AsyncMock()
    close_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    client.get_market.return_value = {
        "market": {
            "ticker": "OPAQUE-MARKET-ID",
            "event_ticker": "OPAQUE-EVENT-ID",
            "status": "open",
            "close_time": close_time,
        }
    }
    client.get_event.return_value = {
        "event": {
            "event_ticker": "OPAQUE-EVENT-ID",
            "series_ticker": "OPAQUE-SERIES-ID",
            "category": category,
        }
    }
    client.get_series.return_value = {
        "series": {
            "ticker": "OPAQUE-SERIES-ID",
            "category": category,
            "tags": tags,
        }
    }
    return client


@pytest.mark.asyncio
async def test_verified_companies_category_blocks_opaque_ticker_at_live_sink():
    client = _verified_market_client(category="Companies", tags=["KPIs"])
    fw = LiveBrokerFirewall(client, ExposureTracker())

    verdict = await fw._verified_live_compliance_verdict(
        _make_request(
            market_ticker="OPAQUE-MARKET-ID",
            contract_ticker="OPAQUE-MARKET-ID",
        )
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "prediction_target_quarantine"
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_rehearsal_never_constructs_order_for_verified_quarantined_target():
    from core.ontology import FirewallVerdict

    client = _verified_market_client(category="Companies", tags=["KPIs"])
    fw = LiveBrokerFirewall(client, ExposureTracker())
    fw.evaluate = AsyncMock(
        return_value=FirewallVerdict(allow=True, reason="replaced preflight")
    )
    original_build = fw._build_order
    fw._build_order = Mock(wraps=original_build)
    ticker = "OPAQUE-MARKET-ID"

    result = await fw.submit_rehearsal(
        _make_request(market_ticker=ticker, contract_ticker=ticker),
        _make_book(),
        _make_forecast(),
    )

    assert result.would_submit is False
    assert result.order is None
    assert result.firewall_verdict.rejected_by == "prediction_target_quarantine"
    fw._build_order.assert_not_called()
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_rehearsal_unverified_target_returns_no_order_shape():
    from core.ontology import FirewallVerdict

    fw = LiveBrokerFirewall(None, ExposureTracker())
    fw.evaluate = AsyncMock(
        return_value=FirewallVerdict(allow=True, reason="replaced preflight")
    )
    original_build = fw._build_order
    fw._build_order = Mock(wraps=original_build)

    result = await fw.submit_rehearsal(
        _make_request(),
        _make_book(),
        _make_forecast(),
    )

    assert result.would_submit is False
    assert result.order is None
    assert result.firewall_verdict.rejected_by == "compliance_metadata"
    fw._build_order.assert_not_called()


@pytest.mark.parametrize(
    ("series_ticker", "tags"),
    [
        ("KXEURUSD", ["Foreign Exchange"]),
        ("KXUST10M", ["Interest Rates"]),
    ],
)
@pytest.mark.asyncio
async def test_verified_financials_fx_and_rates_are_not_equity_quarantined(
    series_ticker,
    tags,
):
    client = _verified_market_client(category="Financials", tags=tags)
    client.get_event.return_value["event"]["series_ticker"] = series_ticker
    client.get_series.return_value["series"]["ticker"] = series_ticker
    fw = LiveBrokerFirewall(client, ExposureTracker())

    verdict = await fw._verified_live_compliance_verdict(
        _make_request(
            market_ticker="OPAQUE-MARKET-ID",
            contract_ticker="OPAQUE-MARKET-ID",
        )
    )

    assert verdict.allow is True
    assert verdict.rejected_by is None
    client.create_order.assert_not_awaited()


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
        assert not v.allow and v.rejected_by == "order_schema"


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
        forecast = _make_forecast()
        v = await fw.evaluate(
            _make_request(forecast=forecast),
            _make_book(),
            forecast,
        )
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
    client.get_orderbook.return_value = _make_book()
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
    from core.ontology import FirewallVerdict

    safety_pass = FirewallVerdict(allow=True, reason="test safety pass")
    with (
        patch("live_firewall.firewall.load_caps", return_value=caps),
        patch.object(LiveBrokerFirewall, "_autonomy_risk_verdict", return_value=safety_pass),
        patch.object(LiveBrokerFirewall, "_canary_readiness_verdict", return_value=safety_pass),
        patch.object(LiveBrokerFirewall, "live_authority_verdict", return_value=safety_pass),
    ):
        fw = LiveBrokerFirewall(client, exposure)
        forecast = _make_forecast()
        result = await fw.submit(
            _make_request(forecast=forecast),
            _make_book(),
            forecast,
        )
        assert result.success
        assert result.order_id == "ord-123"
        assert len(exposure.order_history) == 1
        assert exposure.open_order_count() == 1
        assert exposure.positions == {}
        assert exposure.total_exposure_cents() == 50
        client.create_order.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("live_request", "rejected_by"),
    [
        (_make_request(price_cents=52, liquidity_role="maker"), "execution_role"),
        (
            _make_request(
                price_cents=52,
                size=11,
                liquidity_role="taker",
            ),
            "executable_depth",
        ),
    ],
)
async def test_side_specific_execution_role_requires_fresh_depth(
    live_request, rejected_by
):
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        verdict = await LiveBrokerFirewall(None, ExposureTracker()).evaluate(
            live_request,
            _make_book(),
            _make_forecast(),
        )
    assert verdict.allow is False
    assert verdict.rejected_by == rejected_by


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
    from core.config_loader import load_caps
    caps = load_caps()
    caps.blocked_categories = ["category:Politics"]
    req = _make_request(
        market_ticker="OPAQUE-MARKET-ID",
        contract_ticker="OPAQUE-MARKET-ID",
    )
    client = AsyncMock()
    client.get_market.return_value = {
        "market": {
            "ticker": "OPAQUE-MARKET-ID",
            "event_ticker": "EVENT",
            "status": "open",
            "close_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
    }
    client.get_event.return_value = {
        "event": {
            "event_ticker": "EVENT",
            "series_ticker": "SERIES",
            "category": "Politics",
        }
    }
    client.get_series.return_value = {
        "series": {"ticker": "SERIES", "category": "Politics", "tags": []}
    }
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(client, ExposureTracker())
        verdict = await fw._verified_live_compliance_verdict(req)
    assert not verdict.allow and verdict.rejected_by == "compliance"


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
        contract_ticker="MARKET",
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
        contract_ticker="MARKET",
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
async def test_correlated_exposure_has_independent_cap():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    from core.config_loader import load_caps
    caps = load_caps()
    caps.allowed_markets = ["KXBTC-NEXT"]
    caps.max_market_exposure_cents = 500
    caps.max_correlated_exposure_cents = 300
    caps.max_total_live_exposure_cents = 1000
    exposure = ExposureTracker()
    exposure.update_position(Position(
        market_ticker="KXBTC-EXISTING",
        contract_ticker="KXBTC-EXISTING",
        side="yes",
        quantity=5,
        avg_price_cents=50,
        unrealized_pnl_cents=0,
    ))
    request = _make_request(
        market_ticker="KXBTC-NEXT",
        contract_ticker="KXBTC-NEXT",
        price_cents=50,
        size=2,
    )
    book = _make_book().model_copy(update={
        "market_ticker": "KXBTC-NEXT",
        "contract_ticker": "KXBTC-NEXT",
    })
    forecast = _make_forecast().model_copy(update={
        "market_ticker": "KXBTC-NEXT",
        "contract_ticker": "KXBTC-NEXT",
    })
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, exposure)
        verdict = await fw.evaluate(request, book, forecast)
    assert not verdict.allow and verdict.rejected_by == "correlated_exposure_cap"


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
