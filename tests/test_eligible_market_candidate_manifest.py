from __future__ import annotations

import pytest

from predator_mesh.v13.market_discovery import RealKalshiMarketDiscovery
from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient, ready_bridge


@pytest.mark.asyncio
async def test_eligible_market_candidate_manifest_is_normalized_and_bounded(tmp_path) -> None:
    proof = await RealKalshiMarketDiscovery(
        credential_bridge=ready_bridge(tmp_path),
        read_only_client_factory=FakeRealKalshiReadOnlyClient,
        max_candidates=2,
    ).discover()

    manifest = proof.candidate_manifest()
    assert manifest["candidate_count"] == 1
    assert manifest["max_candidates"] == 2
    assert manifest["candidates"][0]["market_ticker"] == "KXDEMO-LIQUIDITY"
    assert manifest["candidates"][0]["orderbook_nonempty"] is True
    assert manifest["verdict"] == "PASS"
