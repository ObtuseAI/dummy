from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


SECRET_KEY = "kid_test_should_not_leak"
SECRET_PEM = "pem_test_should_not_leak"


def write_dummy_env(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                f"KALSHI_API_KEY_ID={SECRET_KEY}",
                f"KALSHI_API_PRIVATE_KEY_PEM={SECRET_PEM}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def ready_bridge(tmp_path):
    from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge

    env_path = write_dummy_env(tmp_path / "dummy.env")
    return KalshiReadOnlyCredentialBridge(
        env={},
        dummy_env_path=env_path,
        project_env_path=tmp_path / "missing.env",
    )


class FakeRealKalshiReadOnlyClient:
    def __init__(self, *, empty_book: bool = False) -> None:
        self.empty_book = empty_book
        self.called: list[str] = []
        self.request_audit_log: list[dict] = []

    async def get_markets(self) -> list[dict]:
        self.called.append("GET /markets")
        return [
            {
                "ticker": "KXDEMO-LIQUIDITY-YES",
                "market_ticker": "KXDEMO-LIQUIDITY",
                "status": "active",
                "close_time": "2099-01-01T00:00:00Z",
            }
        ]

    async def get_orderbook(self, ticker: str) -> dict:
        self.called.append(f"GET /markets/{ticker}/orderbook")
        if self.empty_book:
            return {
                "ticker": ticker,
                "market_ticker": "KXDEMO-LIQUIDITY",
                "contract_ticker": ticker,
                "bids": [],
                "asks": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "ticker": ticker,
            "market_ticker": "KXDEMO-LIQUIDITY",
            "contract_ticker": ticker,
            "bids": [{"price": 47, "size": 80}, {"price": 46, "size": 40}],
            "asks": [{"price": 51, "size": 90}, {"price": 52, "size": 30}],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def endpoints_called(self) -> set[str]:
        return set(self.called)

    async def close(self) -> None:
        return None


def real_snapshot_result():
    from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult

    return OrderbookSnapshotResult.from_snapshot(
        mode=OrderbookSnapshotMode.REAL_READ_ONLY,
        snapshot={
            "market_ticker": "KXDEMO-LIQUIDITY",
            "contract_ticker": "KXDEMO-LIQUIDITY-YES",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bids": [{"price": 47, "size": 80}],
            "asks": [{"price": 51, "size": 90}],
            "requested_size": 5,
            "expected_edge_cents": 8.0,
        },
        proof_ref="real-orderbook-proof-v13-test",
    )
