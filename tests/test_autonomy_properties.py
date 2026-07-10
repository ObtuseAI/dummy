"""Generated boundary checks for fee, settlement, and public-book invariants."""
from __future__ import annotations

from datetime import date

from hypothesis import HealthCheck, given, settings, strategies as st

from autonomy.fees import (
    FEE_SCHEDULE_EFFECTIVE_DATE,
    kalshi_maker_fee_cents,
    kalshi_taker_fee_cents,
)
from autonomy.reconciler import settlement_pnl_cents
from autonomy.signals.cross_venue import _orderbook_quote


TICKERS = st.sampled_from([
    "KXMLBGAME-26JUL10-ABC",
    "KXHIGHNY-26JUL10-T85",
    "KXBTCY-26DEC31",
    "KXUNKNOWN-26JUL10-X",
])
PROPERTY_SETTINGS = settings(suppress_health_check=[HealthCheck.too_slow])


@PROPERTY_SETTINGS
@given(price=st.integers(1, 99), count=st.integers(0, 500), ticker=TICKERS)
def test_current_maker_fee_never_exceeds_taker_fee(price, count, ticker):
    maker = kalshi_maker_fee_cents(
        price, count, ticker, as_of=FEE_SCHEDULE_EFFECTIVE_DATE,
    )
    taker = kalshi_taker_fee_cents(price, count, ticker)
    assert 0 <= maker <= taker


@PROPERTY_SETTINGS
@given(
    side=st.sampled_from(["yes", "no"]),
    price=st.integers(1, 99),
    count=st.integers(0, 500),
    result_yes=st.booleans(),
    ticker=TICKERS,
)
def test_settlement_pnl_stays_inside_fee_adjusted_contract_bounds(
    side, price, count, result_yes, ticker,
):
    pnl = settlement_pnl_cents(
        side, price, count, result_yes, ticker, liquidity_role="taker",
    )
    fee = kalshi_taker_fee_cents(price, count, ticker)
    assert -price * count - fee <= pnl <= (100 - price) * count
    if count == 0:
        assert pnl == 0


@PROPERTY_SETTINGS
@given(
    bid=st.integers(1, 98),
    width=st.integers(0, 98),
    bid_size=st.integers(0, 100_000),
    ask_size=st.integers(0, 100_000),
)
def test_public_orderbook_midpoint_is_bounded_by_the_spread(
    bid, width, bid_size, ask_size,
):
    ask = min(99, bid + width)
    quote = _orderbook_quote({
        "bids": [{"price": str(bid / 100), "size": str(bid_size)}],
        "asks": [{"price": str(ask / 100), "size": str(ask_size)}],
    })
    assert quote is not None
    assert quote["best_bid"] <= quote["midpoint"] <= quote["best_ask"]
    assert quote["spread"] >= 0
    assert quote["best_bid_size"] == bid_size
    assert quote["best_ask_size"] == ask_size


@PROPERTY_SETTINGS
@given(price=st.integers(1, 99), count=st.integers(0, 500), ticker=TICKERS)
def test_stale_maker_schedule_fails_closed_to_taker(price, count, ticker):
    stale = date(2026, 9, 1)
    assert kalshi_maker_fee_cents(price, count, ticker, as_of=stale) == (
        kalshi_taker_fee_cents(price, count, ticker)
    )
