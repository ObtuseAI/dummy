"""Tests for Kalshi metadata response shape parsing."""

from __future__ import annotations

from core.kalshi_market_validator import _market_metadata_from_api


def test_list_markets_shape_with_markets_key():
    response = {
        "cursor": "abc",
        "markets": [
            {
                "ticker": "KXACTIVE-S2026ABCD-1234",
                "status": "active",
                "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}],
            }
        ],
    }
    markets = response.get("markets", [])
    metadata = _market_metadata_from_api(markets[0])
    assert metadata is not None
    assert metadata.ticker == "KXACTIVE-S2026ABCD-1234"
    assert metadata.status == "open"
    assert metadata.trading_allowed is True
    assert metadata.min_price_cents == 1
    assert metadata.max_price_cents == 99
    assert metadata.tick_size_cents == 1


def test_single_market_shape_unwrapped():
    response = {
        "ticker": "KXACTIVE-S2026ABCD-1234",
        "status": "active",
        "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}],
    }
    metadata = _market_metadata_from_api(response)
    assert metadata is not None
    assert metadata.ticker == "KXACTIVE-S2026ABCD-1234"


def test_single_market_shape_nested_market_key():
    response = {
        "market": {
            "ticker": "KXACTIVE-S2026ABCD-1234",
            "status": "active",
            "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}],
        }
    }
    # _market_metadata_from_api expects the market object itself; callers unwrap.
    metadata = _market_metadata_from_api(response["market"])
    assert metadata is not None
    assert metadata.ticker == "KXACTIVE-S2026ABCD-1234"


def test_legacy_cent_fields_still_supported():
    response = {
        "ticker": "ABC-01JAN30-C",
        "status": "open",
        "trading_allowed": True,
        "min_price_cents": 5,
        "max_price_cents": 99,
        "tick_size_cents": 5,
        "contracts": [{"ticker": "ABC-01JAN30-C", "status": "open", "tradable": True}],
    }
    metadata = _market_metadata_from_api(response)
    assert metadata is not None
    assert metadata.min_price_cents == 5
    assert metadata.tick_size_cents == 5


def test_unsupported_schema_returns_none():
    response = {"unexpected": "shape"}
    metadata = _market_metadata_from_api(response)
    assert metadata is None


def test_missing_ticker_returns_none():
    response = {"status": "active"}
    metadata = _market_metadata_from_api(response)
    assert metadata is None


def test_settled_status_maps_to_closed():
    response = {
        "ticker": "KXSETTLED-S2026ABCD-1234",
        "status": "settled",
        "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}],
    }
    metadata = _market_metadata_from_api(response)
    assert metadata is not None
    assert metadata.status == "closed"
    assert metadata.trading_allowed is False


def test_no_contracts_synthesizes_contract_from_market():
    response = {
        "ticker": "KXACTIVE-S2026ABCD-1234",
        "status": "active",
        "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}],
    }
    metadata = _market_metadata_from_api(response)
    assert metadata is not None
    assert len(metadata.contracts) == 1
    assert metadata.contracts[0].ticker == "KXACTIVE-S2026ABCD-1234"
    assert metadata.contracts[0].status == "open"
    assert metadata.contracts[0].tradable is True


def test_price_ranges_out_of_bounds_are_clamped():
    response = {
        "ticker": "KXCLAMP-S2026ABCD-1234",
        "status": "active",
        "price_ranges": [{"start": "0.0000", "end": "5.0000", "step": "0.0010"}],
    }
    metadata = _market_metadata_from_api(response)
    assert metadata is not None
    assert metadata.max_price_cents == 99
