"""Tests for Kalshi live data normalizer."""

from datetime import datetime, timedelta, timezone

import pytest

from core.ontology import OrderBook, OrderBookLevel
from kalshi.normalizer import KalshiNormalizer, DataNormalizationError


def test_normalize_account():
    raw = {"user_id": "u1", "email": "a@b.com", "balance": 10000, "available_balance": 9000}
    account = KalshiNormalizer().normalize_account(raw)
    assert account.user_id == "u1"
    assert account.balance_cents == 10000
    assert account.available_cents == 9000


def test_normalize_markets():
    raw = {
        "markets": [
            {"ticker": "MKT", "title": "Market", "status": "active", "category": "weather", "event_ticker": "EVT"}
        ]
    }
    markets = KalshiNormalizer().normalize_markets(raw)
    assert len(markets) == 1
    assert markets[0].ticker == "MKT"
    assert markets[0].contracts[0].ticker == "MKT"


def test_normalize_orderbook():
    raw = {
        "ticker": "MKT-YES",
        "bids": [{"price": 48, "size": 10}],
        "asks": [{"price": 52, "size": 10}],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ob = KalshiNormalizer().normalize_orderbook("MKT-YES", raw)
    assert isinstance(ob, OrderBook)
    assert ob.contract_ticker == "MKT-YES"
    assert ob.bids[0].price == 48
    assert ob.asks[0].size == 10


def test_normalize_orderbook_from_model():
    ob_in = OrderBook(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )
    ob = KalshiNormalizer().normalize_orderbook("MKT-YES", ob_in)
    assert ob is ob_in


def test_reject_stale_orderbook():
    stale = datetime.now(timezone.utc) - timedelta(seconds=120)
    raw = {
        "bids": [{"price": 48, "size": 10}],
        "asks": [{"price": 52, "size": 10}],
        "timestamp": stale.isoformat(),
    }
    with pytest.raises(DataNormalizationError, match="stale"):
        KalshiNormalizer().normalize_orderbook("MKT-YES", raw)


def test_reject_malformed_contract():
    raw = {"markets": [{"title": "Market", "status": "active"}]}
    with pytest.raises(DataNormalizationError, match="ticker"):
        KalshiNormalizer().normalize_markets(raw)


def test_normalize_positions():
    raw = {"positions": [{"market_ticker": "MKT", "ticker": "MKT-YES", "side": "yes", "position": 5}]}
    positions = KalshiNormalizer().normalize_positions(raw)
    assert len(positions) == 1
    assert positions[0].quantity == 5


def test_normalize_resting_orders():
    raw = {"orders": [{"order_id": "o1", "market_ticker": "MKT", "ticker": "MKT-YES", "side": "yes", "action": "buy", "type": "limit", "count": 1, "price": 50, "status": "resting", "created_time": datetime.now(timezone.utc).isoformat()}]}
    orders = KalshiNormalizer().normalize_resting_orders(raw)
    assert len(orders) == 1
    assert orders[0].type == "limit"


def test_normalize_fills():
    raw = {"fills": [{"fill_id": "f1", "market_ticker": "MKT", "ticker": "MKT-YES", "side": "yes", "count": 1, "price": 50, "created_time": datetime.now(timezone.utc).isoformat()}]}
    fills = KalshiNormalizer().normalize_fills(raw)
    assert len(fills) == 1
    assert fills[0].price_cents == 50


def test_to_forecast_input():
    from core.ontology import Market, Contract
    market = Market(ticker="MKT", title="Market", status="active", category="weather", event_ticker="EVT", contracts=[Contract(ticker="MKT-YES", title="Yes", status="active", yes_bid=48, yes_ask=52)])
    ob = OrderBook(market_ticker="MKT", contract_ticker="MKT-YES", bids=[OrderBookLevel(price=48, size=10)], asks=[OrderBookLevel(price=52, size=10)], timestamp=datetime.now(timezone.utc))
    fi = KalshiNormalizer().to_forecast_input(market, ob)
    assert fi.market_ticker == "MKT"
    assert fi.yes_bid == 48
    assert fi.yes_ask == 52


def test_normalize_full_snapshot():
    now = datetime.now(timezone.utc)
    snapshot = {
        "account_status": {"user_id": "u1", "balance": 10000, "available_balance": 9000},
        "events": {"events": []},
        "markets": {"markets": [{"ticker": "MKT", "title": "Market", "status": "active", "category": "weather", "event_ticker": "EVT"}]},
        "orderbook": {"ticker": "MKT-YES", "bids": [{"price": 48, "size": 10}], "asks": [{"price": 52, "size": 10}], "timestamp": now.isoformat()},
        "positions": {"positions": []},
        "resting_orders": {"orders": []},
        "fills": {"fills": []},
    }
    normalized = KalshiNormalizer().normalize_full_snapshot(snapshot, "MKT-YES")
    assert "account" in normalized
    assert "orderbook" in normalized
    assert "forecast_input" in normalized
