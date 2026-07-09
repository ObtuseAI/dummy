import pytest

from core.kalshi_market_validator import (
    ContractMetadata,
    MarketMetadata,
    KalshiReadOnlyMetadataClient,
    derive_validated_price,
    discover_live_eligible_candidates,
    validate_order_payload_shape,
    validate_payload_against_metadata,
)


class FakeKalshiClient:
    def __init__(self, markets):
        self._markets = markets

    async def get_markets(self):
        return {"markets": self._markets}

    async def get_market(self, ticker: str):
        for market in self._markets:
            if str(market.get("ticker", "")).upper() == ticker.upper():
                return market
        return None


class FakeHttpxClient:
    async def request(self, method: str, path: str, **kwargs):
        return {"method": method, "path": path}

    async def aclose(self):
        pass


class FakeWrappedKalshiClient:
    """A minimal KalshiClient-shaped fake with a ``.client`` transport."""

    def __init__(self, markets):
        self._markets = markets
        self.client = FakeHttpxClient()
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
        await self.client.aclose()


def _open_market(
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
        "contracts": [
            {"ticker": ticker, "status": "open", "tradable": True}
        ],
    }


@pytest.mark.asyncio
async def test_active_market_produces_candidate_found():
    client = FakeKalshiClient([_open_market()])
    found, metadata, reason = await discover_live_eligible_candidates(client)
    assert found is True
    assert metadata is not None
    assert metadata.ticker == "ABC-01JAN30-C"
    assert reason == "live_eligible_candidate_found"


@pytest.mark.asyncio
async def test_price_validated_when_metadata_has_valid_bounds():
    client = FakeKalshiClient([_open_market(min_price_cents=5, tick_size_cents=5)])
    found, metadata, _ = await discover_live_eligible_candidates(client)
    assert found is True
    price, validated, source = derive_validated_price(metadata)
    assert validated is True
    assert price == 5
    assert "metadata" in source


@pytest.mark.asyncio
async def test_limit_count_one_compatible():
    client = FakeKalshiClient([_open_market()])
    found, metadata, _ = await discover_live_eligible_candidates(client)
    assert found is True
    price, _, _ = derive_validated_price(metadata)
    payload = {
        "ticker": metadata.ticker,
        "side": "yes",
        "action": "buy",
        "type": "LIMIT",
        "count": 1,
        "price": price,
        "client_order_id": "discovery-sample",
    }
    assert validate_order_payload_shape(payload).ok
    assert validate_payload_against_metadata(payload, metadata).ok


@pytest.mark.asyncio
async def test_closed_market_rejected():
    market = _open_market()
    market["status"] = "closed"
    market["trading_allowed"] = False
    client = FakeKalshiClient([market])
    found, metadata, reason = await discover_live_eligible_candidates(client)
    assert found is False
    assert metadata is None
    assert reason == "NO_TRADABLE_MARKETS"


@pytest.mark.asyncio
async def test_closed_contract_rejected():
    market = _open_market()
    market["contracts"][0]["status"] = "closed"
    market["contracts"][0]["tradable"] = False
    client = FakeKalshiClient([market])
    found, metadata, reason = await discover_live_eligible_candidates(client)
    assert found is False
    assert metadata is None
    assert reason == "NO_TRADABLE_CONTRACTS"


@pytest.mark.asyncio
async def test_no_candidate_found():
    client = FakeKalshiClient([])
    found, metadata, reason = await discover_live_eligible_candidates(client)
    assert found is False
    assert metadata is None
    assert reason == "NO_MARKETS_RETURNED"


def test_one_cent_rejected_when_below_allowed_minimum():
    metadata = MarketMetadata(
        ticker="ABC-01JAN30-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=5,
        max_price_cents=99,
        tick_size_cents=5,
        contracts=[
            ContractMetadata(ticker="ABC-01JAN30-C", status="open", tradable=True)
        ],
    )
    payload = {
        "ticker": "ABC-01JAN30-C",
        "side": "yes",
        "action": "buy",
        "type": "LIMIT",
        "count": 1,
        "price": 1,
        "client_order_id": "below-min",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok
    assert any(
        "minimum" in e.lower() or "bounds" in e.lower() for e in result.errors
    )


def test_valid_price_selected_from_metadata():
    metadata = MarketMetadata(
        ticker="ABC-01JAN30-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=7,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ContractMetadata(ticker="ABC-01JAN30-C", status="open", tradable=True)
        ],
    )
    price, validated, source = derive_validated_price(metadata)
    assert validated is True
    assert price == 7
    assert "metadata" in source


def test_market_order_rejected():
    payload = {
        "ticker": "ABC-01JAN30-C",
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
    """The wrapped client transport blocks POST/DELETE at the guard layer."""
    fake = FakeWrappedKalshiClient([_open_market()])
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
