from __future__ import annotations

from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient
from tests.v16_test_helpers import real_discovery


def test_config_bound_discovery_uses_readonly_endpoints_and_finds_candidate() -> None:
    client = FakeRealKalshiReadOnlyClient()
    result = real_discovery(client)

    assert result.mode == "REAL_READ_ONLY_DISCOVERY"
    assert result.eligible_candidate_count == 1
    assert result.eligible_candidates[0].contract_ticker == "KXDEMO-LIQUIDITY-YES"
    assert all(endpoint.startswith("GET ") for endpoint in result.endpoints_called)
    assert result.max_request_timeout_s <= 10
    assert result.total_timeout_s <= 45


def test_config_bound_discovery_keeps_runtime_credentials_available_during_reads() -> None:
    import os

    from predator_mesh.v16.market_discovery import ConfigBoundRealKalshiMarketDiscovery
    from tests.v16_test_helpers import SECRET_KEY, valid_runtime_config

    class EnvAssertingClient(FakeRealKalshiReadOnlyClient):
        async def get_markets(self) -> list[dict]:
            assert os.environ.get("KALSHI_API_KEY_ID") == SECRET_KEY
            return await super().get_markets()

        async def get_orderbook(self, ticker: str) -> dict:
            assert os.environ.get("KALSHI_API_KEY_ID") == SECRET_KEY
            return await super().get_orderbook(ticker)

    result = ConfigBoundRealKalshiMarketDiscovery(
        runtime_config=valid_runtime_config(),
        read_only_client_factory=lambda: EnvAssertingClient(),
    ).discover_sync()

    assert result.mode == "REAL_READ_ONLY_DISCOVERY"
