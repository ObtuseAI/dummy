"""Sample and mock adapters for data inflow discovery.

All adapters are deterministic and make no live external calls by default.
The Kalshi adapter is read-only and returns a stub unless explicitly wired
into a read-only Kalshi client, preserving the Live Broker Firewall.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from predator_mesh.data_inflow.models import DataSourceCandidate, SourceCategory


class BaseDataAdapter(ABC):
    """Abstract adapter that produces one or more source candidates."""

    name: str = "base"
    category: SourceCategory = SourceCategory.UNKNOWN
    adapter_type: str = "base"

    @abstractmethod
    async def fetch(self) -> list[DataSourceCandidate]:
        """Return candidates discovered by this adapter."""
        raise NotImplementedError


class MockDataAdapter(BaseDataAdapter):
    """Deterministic mock adapter for tests and baseline discovery."""

    name = "mock_feed"
    category = SourceCategory.MOCK
    adapter_type = "mock"

    async def fetch(self) -> list[DataSourceCandidate]:
        return [
            DataSourceCandidate(
                name="mock_stable_feed",
                category=SourceCategory.MOCK,
                adapter_type=self.adapter_type,
                reliability=0.9,
                freshness_s=1.0,
                latency_ms=15.0,
                uniqueness=0.5,
                edge_contribution=0.4,
                sample_payload={"type": "synthetic", "version": 1},
            ),
            DataSourceCandidate(
                name="mock_slow_feed",
                category=SourceCategory.MOCK,
                adapter_type=self.adapter_type,
                reliability=0.6,
                freshness_s=30.0,
                latency_ms=800.0,
                uniqueness=0.3,
                edge_contribution=0.2,
                sample_payload={"type": "synthetic", "version": 2},
            ),
        ]


class RSSSampleAdapter(BaseDataAdapter):
    """Sample RSS adapter returning static public headlines.

    No live network calls are made.
    """

    name = "rss_sample"
    category = SourceCategory.RSS
    adapter_type = "rss_sample"

    async def fetch(self) -> list[DataSourceCandidate]:
        return [
            DataSourceCandidate(
                name="public_rss_macro",
                category=SourceCategory.RSS,
                adapter_type=self.adapter_type,
                reliability=0.75,
                freshness_s=60.0,
                latency_ms=120.0,
                uniqueness=0.6,
                edge_contribution=0.45,
                sample_payload={
                    "headline": "Sample public macro headline",
                    "url": "https://example.com/public-sample",
                },
            ),
        ]


class FileSampleAdapter(BaseDataAdapter):
    """Sample file-based adapter returning a static local dataset candidate."""

    name = "file_sample"
    category = SourceCategory.FILE
    adapter_type = "file_sample"

    async def fetch(self) -> list[DataSourceCandidate]:
        return [
            DataSourceCandidate(
                name="local_sample_csv",
                category=SourceCategory.FILE,
                adapter_type=self.adapter_type,
                reliability=0.85,
                freshness_s=300.0,
                latency_ms=5.0,
                uniqueness=0.4,
                edge_contribution=0.3,
                sample_payload={"path": "data/sample_public.csv", "rows": 100},
            ),
        ]


class KalshiReadOnlyAdapter(BaseDataAdapter):
    """Read-only Kalshi adapter.

    This adapter never places orders and never exposes raw account data.
    With no injected client it returns an explicitly empty snapshot; a real
    read-only client may be injected via ``set_client`` for the proven Kalshi
    READ_ONLY path. Empty data is not promoted into terrain evidence.
    """

    name = "kalshi_readonly"
    category = SourceCategory.KALSHI
    adapter_type = "kalshi_readonly"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def set_client(self, client: Any) -> None:
        """Wire in a read-only Kalshi client."""
        self._client = client

    async def fetch(self) -> list[DataSourceCandidate]:
        snapshot: dict[str, Any] = {"markets": []}
        if self._client is not None:
            snapshot = await self._client.read_markets()
        return [
            DataSourceCandidate(
                name="kalshi_market_terrain",
                category=SourceCategory.KALSHI,
                adapter_type=self.adapter_type,
                reliability=0.88,
                freshness_s=10.0,
                latency_ms=250.0,
                uniqueness=0.7,
                edge_contribution=0.55,
                sample_payload=snapshot,
            ),
        ]
