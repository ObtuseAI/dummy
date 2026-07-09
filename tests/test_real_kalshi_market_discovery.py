from __future__ import annotations

import pytest

from predator_mesh.v13.market_discovery import MarketDiscoveryMode, RealKalshiMarketDiscovery
from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient, ready_bridge


@pytest.mark.asyncio
async def test_real_kalshi_market_discovery_finds_open_market_with_nonempty_orderbook(tmp_path) -> None:
    client = FakeRealKalshiReadOnlyClient()
    discovery = RealKalshiMarketDiscovery(
        credential_bridge=ready_bridge(tmp_path),
        read_only_client_factory=lambda: client,
        max_candidates=3,
    )

    proof = await discovery.discover()

    assert proof.mode is MarketDiscoveryMode.REAL_READ_ONLY_DISCOVERY
    assert proof.eligible_candidates
    assert proof.eligible_candidates[0].contract_ticker == "KXDEMO-LIQUIDITY-YES"
    assert "GET /markets" in client.called
