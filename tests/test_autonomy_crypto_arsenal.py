"""Crypto Phase 1a: DVOL implied book, Kraken vol failover, event windows."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.crypto_events import (
    EVENT_UNCERTAINTY_BUMP,
    active_bump,
    active_event,
)
from autonomy.crypto_implied_book import CryptoImpliedBook
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_indicators import CryptoDataHub
from autonomy.signals.crypto_spot import (
    _normal_cdf,
    crypto_probability_uncertainty,
)

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _crypto_market(ticker: str, hours: float = 24.0, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title="crypto?", vertical=Vertical.CRYPTO, status="open",
        close_time=(NOW + timedelta(hours=hours)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=100, liquidity=1_000, raw=raw,
    )


# -- implied book --------------------------------------------------------------

def _book(state: dict, hours: float = 24.0) -> CryptoImpliedBook:
    return CryptoImpliedBook(lambda _asset: state, hours_to_close=lambda _m: hours)


def test_implied_book_prices_floor_strike_from_dvol():
    book = _book({"dvol": 50.0, "spot": 71_000.0}, hours=24.0)
    market = _crypto_market(
        "KXBTCD-26JUL1317-T70000", strike_type="greater", floor_strike=70_000.0,
    )
    sigma = 0.50 * math.sqrt(24.0 / (24 * 365))
    expected = _normal_cdf(math.log(71_000.0 / 70_000.0) / sigma)
    assert book.book_probability(market) == pytest.approx(expected, abs=1e-9)
    assert 0.70 < expected < 0.72  # sanity: z ~= 0.542


def test_implied_book_mirrors_every_strike_shape():
    state = {"dvol": 50.0, "spot": 71_000.0}
    book = _book(state)
    p_floor = book.book_probability(_crypto_market(
        "KXBTCD-26JUL1317-T70000", strike_type="greater", floor_strike=70_000.0))
    p_less = book.book_probability(_crypto_market(
        "KXBTCD-26JUL1317-T70000", strike_type="less", cap_strike=70_000.0))
    assert p_less == pytest.approx(1.0 - p_floor, abs=1e-9)
    p_between = book.book_probability(_crypto_market(
        "KXBTCD-26JUL1317-T70000", strike_type="between",
        floor_strike=70_000.0, cap_strike=72_000.0))
    assert 0.0 < p_between < p_floor
    # No strike_type payload -> the parsed ticker threshold prices the book.
    p_parsed = book.book_probability(_crypto_market("KXBTCD-26JUL1317-T70000"))
    assert p_parsed == pytest.approx(p_floor, abs=1e-9)


def test_implied_book_fails_closed():
    market = _crypto_market(
        "KXBTCD-26JUL1317-T70000", strike_type="greater", floor_strike=70_000.0)
    assert _book({"dvol": None, "spot": 71_000.0}).book_probability(market) is None
    assert _book({"spot": 71_000.0}).book_probability(market) is None
    assert _book({"dvol": 50.0, "spot": 0.0}).book_probability(market) is None
    assert _book({"dvol": -1.0, "spot": 71_000.0}).book_probability(market) is None

    def _raising_state(_asset):
        raise ValueError("hub down")

    assert CryptoImpliedBook(_raising_state).book_probability(market) is None
    # Non-crypto ticker: not this book's market.
    assert _book({"dvol": 50.0, "spot": 71_000.0}).book_probability(
        MarketView(
            ticker="KXMLBGAME-26JUL122005HOUTEX-HOU", title="mlb", vertical=Vertical.SPORTS,
            status="open", close_time=NOW.isoformat(), yes_bid=44, yes_ask=46,
            no_bid=54, no_ask=56, volume=1, liquidity=1, raw={},
        )
    ) is None


# -- kraken hourly failover -----------------------------------------------------

class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _ScriptedClient:
    """Serves canned payloads per URL substring; records every URL hit."""

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url, params=None):
        self.calls.append(url)
        for key, payload in self.routes.items():
            if key in url:
                value = payload() if callable(payload) else payload
                if isinstance(value, Exception):
                    raise value
                return _Response(value)
        raise AssertionError(f"unrouted url {url}")

    def close(self):
        return None


def _coinbase_hourly(now_s: float, count: int = 60):
    # Coinbase rows: [time, low, high, open, close, volume], newest last after sort.
    return [
        [int(now_s - 3600 * (count - index)), 100.0, 102.0, 101.0,
         70_000.0 + index, 5.0]
        for index in range(count)
    ]


def _kraken_ohlc(now_s: float, count: int = 60):
    rows = [
        [int(now_s - 3600 * (count - index)), "101", "102", "100",
         str(69_500.0 + index), "100.5", "7.5", 12]
        for index in range(count)
    ]
    return {"error": [], "result": {"XXBTZUSD": rows, "last": int(now_s)}}


_EMPTY_BOOK = {"bids": [], "asks": []}
_KRAKEN_TICKER = {"error": [], "result": {"XXBTZUSD": {"c": ["70050.0", "1"]}}}
_DVOL = {"result": {"data": []}}


def test_hub_uses_coinbase_when_healthy_and_never_calls_kraken_ohlc():
    now_s = 1_800_000_000.0
    client = _ScriptedClient({
        "candles": _coinbase_hourly(now_s),
        "book": _EMPTY_BOOK,
        "Ticker": _KRAKEN_TICKER,
        "get_volatility_index_data": _DVOL,
    })
    hub = CryptoDataHub(client_factory=lambda: client, now_s=lambda: now_s)
    state = hub.state("BTC")
    assert state["hourly_source"] == "coinbase"
    assert not any("OHLC" in url for url in client.calls)
    assert state["hourly_closes"][-1] == pytest.approx(70_059.0)


def test_hub_fails_over_to_kraken_when_coinbase_hourly_is_stale():
    now_s = 1_800_000_000.0
    stale = _coinbase_hourly(now_s - 8 * 3600)  # 8h old -> fails the 3h gate
    client = _ScriptedClient({
        "candles": stale,
        "OHLC": _kraken_ohlc(now_s),
        "book": _EMPTY_BOOK,
        "Ticker": _KRAKEN_TICKER,
        "get_volatility_index_data": _DVOL,
    })
    hub = CryptoDataHub(client_factory=lambda: client, now_s=lambda: now_s)
    state = hub.state("BTC")
    assert state["hourly_source"] == "kraken"
    assert any("OHLC" in url for url in client.calls)
    assert state["hourly_closes"][-1] == pytest.approx(69_559.0)
    # Realized vol still computes from the failover closes.
    spot, vol = hub.flat_spot_and_vol("BTC")
    assert spot > 0 and vol > 0


def test_hub_raises_only_when_both_hourly_sources_fail():
    now_s = 1_800_000_000.0
    client = _ScriptedClient({
        "candles": ValueError("coinbase down"),
        "OHLC": ValueError("kraken down"),
    })
    hub = CryptoDataHub(client_factory=lambda: client, now_s=lambda: now_s)
    with pytest.raises(ValueError, match="insufficient hourly crypto history"):
        hub.state("BTC")


# -- event windows ---------------------------------------------------------------

def test_event_windows_widen_uncertainty_only_inside_the_window():
    inside = datetime(2026, 7, 28, 19, 0, tzinfo=timezone.utc)  # FOMC decision day
    outside = datetime(2026, 7, 12, 19, 0, tzinfo=timezone.utc)
    assert active_event(inside) == "FOMC"
    assert active_event(outside) is None
    assert active_bump(inside) == EVENT_UNCERTAINTY_BUMP
    assert active_bump(outside) == 0.0

    base = crypto_probability_uncertainty(0.5, 0.01)
    bumped = crypto_probability_uncertainty(0.5, 0.01, event_bump=active_bump(inside))
    unchanged = crypto_probability_uncertainty(0.5, 0.01, event_bump=active_bump(outside))
    assert bumped == pytest.approx(base + EVENT_UNCERTAINTY_BUMP)
    assert unchanged == base  # byte-identical outside every window
    # The bump can never push uncertainty past the model ceiling.
    assert crypto_probability_uncertainty(0.5, 1.0, event_bump=1.0) == 0.35
