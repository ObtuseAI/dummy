import pytest
from core.kalshi_market_validator import (
    validate_ticker_shape,
    validate_order_payload_shape,
    validate_payload_against_metadata,
    MarketMetadata,
    ContractMetadata,
)


def test_malformed_market_ticker_rejected():
    result = validate_ticker_shape("")
    assert not result.ok
    assert "market_ticker" in result.errors[0].lower()


def test_missing_contract_rejected():
    result = validate_ticker_shape("KXBTC-26DEC25000-C", contract_ticker="")
    assert not result.ok


def test_market_order_rejected():
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "market",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_order_payload_shape(payload)
    assert not result.ok
    assert any("limit" in e.lower() for e in result.errors)


def test_count_greater_than_one_rejected():
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 2,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_order_payload_shape(payload)
    assert not result.ok


def test_price_outside_bounds_rejected():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 0,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok


def test_closed_market_rejected():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="closed",
        open_time=None,
        close_time=None,
        trading_allowed=False,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="closed", tradable=False)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok
    assert any("open" in e.lower() or "trad" in e.lower() for e in result.errors)


def test_valid_payload_accepted():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert result.ok
