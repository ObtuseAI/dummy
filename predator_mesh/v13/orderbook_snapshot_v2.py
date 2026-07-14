"""V13 real orderbook snapshot closure over V12 adapter primitives."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from predator_mesh.v12.orderbook_snapshot import (
    OrderbookSnapshotMode,
    OrderbookSnapshotRequest,
    OrderbookSnapshotResult,
    RealKalshiOrderbookSnapshotAdapter,
)
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2
from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.market_discovery import MarketDiscoveryMode, MarketDiscoveryProof, RealKalshiMarketDiscovery


@dataclass(frozen=True)
class RealOrderbookSnapshotClosure:
    snapshot_result: OrderbookSnapshotResult
    discovery: MarketDiscoveryProof
    outcome: str
    credential_status: dict[str, Any]

    @property
    def snapshot_mode(self) -> str:
        return self.snapshot_result.mode.value

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V13: Real Kalshi Orderbook Snapshot Adapter V2",
            "outcome": self.outcome,
            "snapshot_mode": self.snapshot_mode,
            "real_read_only_succeeded": self.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY,
            "credential_status": self.credential_status,
            "market_discovery_mode": self.discovery.mode.value,
            "selected_candidate": (
                self.discovery.selected_candidate.to_dict() if self.discovery.selected_candidate else None
            ),
            "snapshot": self.snapshot_result.to_dict(),
            "request_timeout_s": self.snapshot_result.proof.request_timeout_s,
            "adapter_timeout_s": self.snapshot_result.proof.adapter_timeout_s,
            "order_endpoints_called": self.snapshot_result.proof.order_endpoints_called,
            "cancel_endpoints_called": self.snapshot_result.proof.cancel_endpoints_called,
            "write_methods_used": self.snapshot_result.proof.write_methods_used,
            "verdict": "PASS" if self.outcome == "REAL_READ_ONLY" else "PARTIAL",
        }

    def mode_report(self) -> dict[str, Any]:
        counts = {mode.value: 0 for mode in OrderbookSnapshotMode}
        counts[self.snapshot_result.mode.value] += 1
        return {
            "workstream": "V13: Orderbook Snapshot Modes V2",
            "mode_counts": counts,
            "active_modes": [self.snapshot_result.mode.value],
            "outcome": self.outcome,
            "partial_reason": "" if self.outcome == "REAL_READ_ONLY" else self.outcome,
            "verdict": "PASS" if self.outcome == "REAL_READ_ONLY" else "PARTIAL",
        }

    def manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V13: Real Orderbook Snapshot Manifest",
            "snapshot_count": 1,
            "snapshots": [
                {
                    "snapshot_mode": self.snapshot_result.mode.value,
                    "real_read_only": self.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                    "market_ticker": self.snapshot_result.snapshot.get("market_ticker"),
                    "contract_ticker": self.snapshot_result.snapshot.get("contract_ticker"),
                    "proof_ref": self.snapshot_result.proof.proof_ref,
                }
            ],
            "verdict": "PASS" if self.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY else "PARTIAL",
        }


class RealKalshiOrderbookSnapshotAdapterV2:
    def __init__(
        self,
        *,
        credential_bridge: KalshiReadOnlyCredentialBridge | None = None,
        read_only_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.credential_bridge = credential_bridge or KalshiReadOnlyCredentialBridge()
        self.read_only_client_factory = read_only_client_factory

    async def capture(self) -> RealOrderbookSnapshotClosure:
        readiness = self.credential_bridge.resolve()
        discovery = await RealKalshiMarketDiscovery(
            credential_bridge=self.credential_bridge,
            read_only_client_factory=self.read_only_client_factory,
        ).discover()
        if not readiness.ready:
            result = OrderbookLiquidityModelV2().fallback_result()
            return RealOrderbookSnapshotClosure(result, discovery, "CREDENTIALS_MISSING", readiness.to_dict())
        if discovery.mode is MarketDiscoveryMode.SAMPLE_STATIC_FALLBACK:
            result = OrderbookLiquidityModelV2().fallback_result()
            return RealOrderbookSnapshotClosure(result, discovery, discovery.degradation_reason, readiness.to_dict())
        if not discovery.selected_candidate:
            result = OrderbookLiquidityModelV2().fallback_result()
            outcome = discovery.degradation_reason or "NO_ELIGIBLE_MARKET_FOUND"
            return RealOrderbookSnapshotClosure(result, discovery, outcome, readiness.to_dict())

        request = OrderbookSnapshotRequest(
            contract_ticker=discovery.selected_candidate.contract_ticker,
            market_ticker=discovery.selected_candidate.market_ticker,
        )
        client_factory = self.read_only_client_factory
        client = client_factory() if client_factory is not None else None
        adapter = RealKalshiOrderbookSnapshotAdapter(read_only_client=client)
        if client is None:
            with self.credential_bridge.credential_environment_overlay():
                result = await adapter.capture(request)
        else:
            result = await adapter.capture(request)
        outcome = self._outcome(result, discovery)
        return RealOrderbookSnapshotClosure(result, discovery, outcome, readiness.to_dict())

    def capture_sync(self) -> RealOrderbookSnapshotClosure:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.capture())
        raise RuntimeError(f"capture_sync cannot run inside active event loop {id(loop)}")

    def _outcome(self, result: OrderbookSnapshotResult, discovery: MarketDiscoveryProof) -> str:
        if result.mode is OrderbookSnapshotMode.REAL_READ_ONLY:
            return "REAL_READ_ONLY"
        reason = result.proof.fallback_reason or discovery.degradation_reason
        if "credential" in reason.lower():
            return "CREDENTIALS_INVALID"
        if reason == "empty_orderbook":
            return "EMPTY_ORDERBOOK_REAL_READ_ONLY"
        if reason == "malformed_orderbook":
            return "MALFORMED_ORDERBOOK_REAL_READ_ONLY"
        if discovery.degradation_reason:
            return discovery.degradation_reason
        return "NO_ELIGIBLE_MARKET_FOUND"


def capture_v13_snapshot_once() -> RealOrderbookSnapshotClosure:
    return RealKalshiOrderbookSnapshotAdapterV2().capture_sync()
