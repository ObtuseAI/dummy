"""V3 read-only Kalshi discovery tests.

Covers dynamic candidate discovery, explicit validation, price derivation,
response-shape support, and read-only guard invariants.
"""

from __future__ import annotations

import pytest

from core.kalshi_market_validator import (
    ContractMetadata,
    KalshiReadOnlyMetadataClient,
    MarketMetadata,
    _classify_discovery_exception,
    _market_metadata_from_api,
    _normalize_market_status,
    _price_bounds_from_ranges,
    derive_validated_price,
    discover_live_eligible_candidates,
    validate_order_payload_shape,
    validate_payload_against_metadata,
)


class FakeKalshiClient:
    def __init__(self, markets=None, market_by_ticker=None):
        self._markets = markets or []
        self._market_by_ticker = market_by_ticker or {}
        self.request_audit_log: list[dict] = []

    async def get_markets(self):
        return {"markets": self._markets}

    async def get_market(self, ticker: str):
        return self._market_by_ticker.get(ticker.upper())


class FakeWrappedKalshiClient:
    """A minimal KalshiClient-shaped fake with a ``.client`` transport."""

    def __init__(self, markets=None):
        self._markets = markets or []
        self.client = object()
        self.request_audit_log: list[dict] = []

    async def get_markets(self):
        return {"markets": self._markets}

    async def get_market(self, ticker: str):
        for market in self._markets:
            if str(market.get("ticker", "")).upper() == ticker.upper():
                return market
        return None

    async def create_order(self, order: dict):
        return await self.client.request("POST", "/portfolio/orders", json=order)

    async def cancel_order(self, order_id: str):
        return await self.client.request("DELETE", f"/portfolio/orders/{order_id}")

    async def close(self):
        pass


def _kalshi_v2_market(
    ticker: str = "KXMVESPORTSMULTIGAMEEXTENDED-S2026ABCD-1234",
    status: str = "active",
    start_dollars: str = "0.0000",
    end_dollars: str = "1.0000",
    step_dollars: str = "0.0010",
):
    return {
        "ticker": ticker,
        "status": status,
        "market_type": "binary",
        "price_level_structure": "deci_cent",
        "response_price_units": "usd_cent",
        "price_ranges": [{"start": start_dollars, "end": end_dollars, "step": step_dollars}],
    }


def _legacy_market(
    ticker: str = "ABC-01JAN30-C",
    min_price_cents: int = 1,
    tick_size_cents: int = 1,
):
    return {
        "ticker": ticker,
        "status": "open",
        "trading_allowed": True,
        "min_price_cents": min_price_cents,
        "max_price_cents": 99,
        "tick_size_cents": tick_size_cents,
        "contracts": [{"ticker": ticker, "status": "open", "tradable": True}],
    }


@pytest.mark.asyncio
async def test_broad_discovery_selects_first_tradable_v2_candidate():
    client = FakeKalshiClient([_kalshi_v2_market()])
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is True
    assert metadata is not None
    assert metadata.status == "open"
    assert metadata.trading_allowed is True
    assert metadata.min_price_cents == 1
    assert metadata.tick_size_cents == 1
    assert reason == "live_eligible_candidate_found"


@pytest.mark.asyncio
async def test_broad_discovery_skips_closed_markets():
    markets = [
        _kalshi_v2_market(status="settled"),
        _kalshi_v2_market(ticker="KXOPEN-S2026ABCD-5678", status="active"),
    ]
    client = FakeKalshiClient(markets)
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is True
    assert metadata is not None
    assert metadata.ticker == "KXOPEN-S2026ABCD-5678"


@pytest.mark.asyncio
async def test_broad_discovery_skips_expired_markets():
    markets = [
        _kalshi_v2_market(status="expired"),
        _kalshi_v2_market(ticker="KXOPEN-S2026ABCD-5678", status="active"),
    ]
    client = FakeKalshiClient(markets)
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is True
    assert metadata.ticker == "KXOPEN-S2026ABCD-5678"


@pytest.mark.asyncio
async def test_broad_discovery_unparseable_market_emits_fallback_blocker():
    market = _kalshi_v2_market(step_dollars="0.0000")
    client = FakeKalshiClient([market])
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is False
    assert metadata is None
    assert reason == "NO_LIVE_ELIGIBLE_CANDIDATE_FOUND"


def test_derive_validated_price_rejects_invalid_bounds():
    metadata = MarketMetadata(
        ticker="KXBAD-S2026ABCD-1234",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=0,
        contracts=[ContractMetadata(ticker="KXBAD-S2026ABCD-1234", status="open", tradable=True)],
    )
    price, validated, source = derive_validated_price(metadata)
    assert validated is False
    assert "metadata_unavailable" in source


@pytest.mark.asyncio
async def test_broad_discovery_no_tradable_contracts_emits_exact_blocker():
    market = _kalshi_v2_market()
    market["status"] = "halted"
    client = FakeKalshiClient([market])
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is False
    assert reason == "NO_TRADABLE_MARKETS"


@pytest.mark.asyncio
async def test_broad_discovery_no_markets_returned():
    client = FakeKalshiClient([])
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is False
    assert reason == "NO_MARKETS_RETURNED"


@pytest.mark.asyncio
async def test_broad_discovery_unsupported_schema():
    client = FakeKalshiClient([{"unexpected": "shape"}])
    found, metadata, reason = await discover_live_eligible_candidates(client, max_candidates=20)
    assert found is False
    assert reason == "NO_LIVE_ELIGIBLE_CANDIDATE_FOUND"


@pytest.mark.asyncio
async def test_explicit_valid_ticker_passes():
    market = _kalshi_v2_market(ticker="KXVALID-S2026ABCD-1234")
    client = FakeKalshiClient(market_by_ticker={"KXVALID-S2026ABCD-1234": {"market": market}})
    found, metadata, reason = await discover_live_eligible_candidates(client)
    # discover_live_eligible_candidates is broad; explicit path uses _fetch_explicit_market_metadata_v3
    # Here we test the underlying get_market + metadata parsing.
    wrapped = KalshiReadOnlyMetadataClient.__new__(KalshiReadOnlyMetadataClient)
    wrapped._client = client
    raw = await wrapped.get_market("KXVALID-S2026ABCD-1234")
    metadata = _market_metadata_from_api(raw)
    assert metadata is not None
    assert metadata.ticker == "KXVALID-S2026ABCD-1234"
    assert metadata.status == "open"
    assert metadata.trading_allowed is True


@pytest.mark.asyncio
async def test_explicit_invalid_ticker_returns_none():
    client = FakeKalshiClient(market_by_ticker={})
    wrapped = KalshiReadOnlyMetadataClient.__new__(KalshiReadOnlyMetadataClient)
    wrapped._client = client
    raw = await wrapped.get_market("MISSING")
    assert raw is None


def test_price_derivation_from_v2_ranges():
    metadata = _market_metadata_from_api(_kalshi_v2_market())
    assert metadata is not None
    price, validated, source = derive_validated_price(metadata)
    assert validated is True
    assert price == 1
    assert "metadata" in source


def test_price_rejected_when_below_min():
    metadata = MarketMetadata(
        ticker="KXLOW-S2026ABCD-1234",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=5,
        max_price_cents=99,
        tick_size_cents=5,
        contracts=[ContractMetadata(ticker="KXLOW-S2026ABCD-1234", status="open", tradable=True)],
    )
    payload = {
        "ticker": "KXLOW-S2026ABCD-1234",
        "side": "yes",
        "action": "buy",
        "type": "LIMIT",
        "count": 1,
        "price": 1,
        "client_order_id": "below-min",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok
    assert any("bounds" in e.lower() for e in result.errors)


def test_price_respects_tick_increment():
    metadata = MarketMetadata(
        ticker="KXTICK-S2026ABCD-1234",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=5,
        max_price_cents=99,
        tick_size_cents=5,
        contracts=[ContractMetadata(ticker="KXTICK-S2026ABCD-1234", status="open", tradable=True)],
    )
    price, validated, _ = derive_validated_price(metadata)
    assert validated is True
    assert price == 5
    payload = {
        "ticker": "KXTICK-S2026ABCD-1234",
        "side": "yes",
        "action": "buy",
        "type": "LIMIT",
        "count": 1,
        "price": price,
        "client_order_id": "on-tick",
    }
    assert validate_order_payload_shape(payload).ok
    assert validate_payload_against_metadata(payload, metadata).ok


def test_market_order_rejected():
    payload = {
        "ticker": "KXMVESPORTSMULTIGAMEEXTENDED-S2026ABCD-1234",
        "side": "yes",
        "action": "buy",
        "type": "market",
        "count": 1,
        "price": 1,
        "client_order_id": "market-order",
    }
    result = validate_order_payload_shape(payload)
    assert not result.ok
    assert any("limit" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_read_only_metadata_client_blocks_writes():
    fake = FakeWrappedKalshiClient([_legacy_market()])
    wrapped = KalshiReadOnlyMetadataClient(client=fake)
    assert wrapped.blocked_attempts == []

    with pytest.raises(RuntimeError, match="POST"):
        await wrapped._client.create_order({"ticker": "ABC-01JAN30-C"})
    assert len(wrapped.blocked_attempts) == 1
    assert wrapped.blocked_attempts[0]["method"] == "POST"

    with pytest.raises(RuntimeError, match="DELETE"):
        await wrapped._client.cancel_order("order-123")
    assert len(wrapped.blocked_attempts) == 2
    assert wrapped.blocked_attempts[1]["method"] == "DELETE"

    await wrapped.close()


def test_classify_401_as_auth():
    import httpx

    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    class FakeRequest:
        url = "https://example.com"
        method = "GET"

    exc = httpx.HTTPStatusError("401", request=FakeRequest(), response=FakeResponse())
    assert _classify_discovery_exception(exc) == "AUTH_OR_NETWORK_BLOCKED"


def test_classify_404_as_metadata_unavailable():
    import httpx

    class FakeResponse:
        status_code = 404
        text = "not found"

    class FakeRequest:
        url = "https://example.com"
        method = "GET"

    exc = httpx.HTTPStatusError("404", request=FakeRequest(), response=FakeResponse())
    assert _classify_discovery_exception(exc) == "MARKET_METADATA_UNAVAILABLE"


def test_normalize_status_maps_active_to_open():
    assert _normalize_market_status("active") == "open"
    assert _normalize_market_status("open") == "open"
    assert _normalize_market_status("settled") == "closed"
    assert _normalize_market_status("halted") == "closed"


def test_price_bounds_from_ranges_parses_deci_cent():
    min_cents, max_cents, tick_cents = _price_bounds_from_ranges(
        [{"start": "0.0000", "end": "1.0000", "step": "0.0010"}]
    )
    assert min_cents == 1
    assert max_cents == 99
    assert tick_cents == 1


def test_price_bounds_from_ranges_parses_cent():
    min_cents, max_cents, tick_cents = _price_bounds_from_ranges(
        [{"start": "0.0100", "end": "0.9900", "step": "0.0100"}]
    )
    assert min_cents == 1
    assert max_cents == 99
    assert tick_cents == 1
