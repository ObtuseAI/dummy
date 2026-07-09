from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient

SECRET_KEY = "v16_kid_test_should_not_leak"
SECRET_PEM = "-----BEGIN PRIVATE KEY-----\nv16-pem-test-should-not-leak\n-----END PRIVATE KEY-----"

VALID_ENV = {
    "KALSHI_API_KEY_ID": SECRET_KEY,
    "KALSHI_API_PRIVATE_KEY_PEM": SECRET_PEM,
    "KALSHI_API_BASE": "https://trading-api.kalshi.example",
    "KALSHI_API_VERSION": "v2",
}

MISSING_ENV: dict[str, str] = {}


def write_dummy_env(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                f"KALSHI_API_KEY_ID={SECRET_KEY}",
                "KALSHI_API_PRIVATE_KEY_PEM=__redacted_test_placeholder__",
                "KALSHI_API_BASE=https://trading-api.kalshi.example",
                "KALSHI_API_VERSION=v2",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


class OneSidedRealKalshiReadOnlyClient(FakeRealKalshiReadOnlyClient):
    async def get_orderbook(self, ticker: str) -> dict:
        self.called.append(f"GET /markets/{ticker}/orderbook")
        return {
            "ticker": ticker,
            "market_ticker": "KXDEMO-LIQUIDITY",
            "contract_ticker": ticker,
            "bids": [{"price": 47, "size": 80}],
            "asks": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class CrossedRealKalshiReadOnlyClient(FakeRealKalshiReadOnlyClient):
    async def get_orderbook(self, ticker: str) -> dict:
        self.called.append(f"GET /markets/{ticker}/orderbook")
        return {
            "ticker": ticker,
            "market_ticker": "KXDEMO-LIQUIDITY",
            "contract_ticker": ticker,
            "bids": [{"price": 55, "size": 80}],
            "asks": [{"price": 51, "size": 90}],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class NoMarketKalshiReadOnlyClient(FakeRealKalshiReadOnlyClient):
    async def get_markets(self) -> list[dict]:
        self.called.append("GET /markets")
        return []


def valid_runtime_config():
    from predator_mesh.v16.runtime_config import KalshiReadOnlyConfigResolver

    return KalshiReadOnlyConfigResolver(env=VALID_ENV).resolve()


def missing_runtime_config():
    from predator_mesh.v16.runtime_config import KalshiReadOnlyConfigResolver

    return KalshiReadOnlyConfigResolver(env=MISSING_ENV, dummy_env_path="__missing_dummy_env__", project_env_path="__missing_project_env__").resolve()


def real_discovery(client: FakeRealKalshiReadOnlyClient | None = None):
    from predator_mesh.v16.market_discovery import ConfigBoundRealKalshiMarketDiscovery

    client = client or FakeRealKalshiReadOnlyClient()
    return ConfigBoundRealKalshiMarketDiscovery(
        runtime_config=valid_runtime_config(),
        read_only_client_factory=lambda: client,
    ).discover_sync()


def real_snapshot(client: FakeRealKalshiReadOnlyClient | None = None):
    from predator_mesh.v16.orderbook_snapshot import ConfigBoundRealOrderbookSnapshotAdapter

    client = client or FakeRealKalshiReadOnlyClient()
    discovery = real_discovery(client)
    return ConfigBoundRealOrderbookSnapshotAdapter(
        runtime_config=valid_runtime_config(),
        discovery_result=discovery,
        read_only_client_factory=lambda: client,
    ).capture_sync()


def pass_truth_verdict():
    from predator_mesh.v16.terrain_truth import RealTerrainTruthInput, RealTerrainTruthResolver

    snapshot = real_snapshot()
    return RealTerrainTruthResolver(
        RealTerrainTruthInput(
            credential_shape_state="SHAPE_VALID",
            auth_probe_state="AUTH_PASS",
            config_binding_state="PASS",
            market_discovery_state="REAL_READ_ONLY_DISCOVERY",
            eligible_market_candidate_count=1,
            orderbook_snapshot_state=snapshot.mode.value,
            nonempty_book_proof=snapshot.nonempty_proof.nonempty,
            read_only_endpoint_audit=True,
            replay_state="REAL_SNAPSHOT_REPLAY",
            fallback_state="NOT_USED",
            artifact_freshness="FRESH",
        )
    ).resolve()
