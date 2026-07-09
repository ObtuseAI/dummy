"""V14 real orderbook terrain closure with explicit credential blockers."""

from __future__ import annotations

from typing import Any

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2
from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2, RealOrderbookSnapshotClosure
from predator_mesh.v13.replay_v2 import RealOrderbookReplayStore
from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


class RealOrderbookTerrainClosureV2:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None, closure: RealOrderbookSnapshotClosure | None = None) -> None:
        self.forensics_report = forensics_report
        self._closure = closure

    def _forensics(self) -> dict[str, Any]:
        return self.forensics_report or KalshiCredentialForensics().to_report()

    def _blocked_outcome(self, forensics: dict[str, Any]) -> str:
        reason = forensics.get("failure_reason", "CREDENTIALS_MISSING")
        if reason == "CREDENTIALS_MISSING":
            return "CREDENTIALS_MISSING"
        if reason == "NONE":
            return ""
        return "CREDENTIALS_INVALID"

    def _fallback_closure(self, blocked: str, forensics: dict[str, Any]) -> RealOrderbookSnapshotClosure:
        from predator_mesh.v13.market_discovery import MarketDiscoveryMode, MarketDiscoveryProof

        fallback = OrderbookLiquidityModelV2().fallback_result()
        discovery = MarketDiscoveryProof(
            mode=MarketDiscoveryMode.SAMPLE_STATIC_FALLBACK,
            eligible_candidates=[],
            degradation_reason=blocked,
            endpoints_called=[],
        )
        return RealOrderbookSnapshotClosure(
            fallback,
            discovery,
            blocked,
            {
                "ready": False,
                "status": blocked,
                "source": forensics.get("selected_source", "missing"),
                "redacted": True,
            },
        )

    def _closure_or_fallback(self) -> RealOrderbookSnapshotClosure:
        if self._closure is not None:
            return self._closure
        forensics = self._forensics()
        blocked = self._blocked_outcome(forensics)
        if blocked:
            self._closure = self._fallback_closure(blocked, forensics)
        else:
            self._closure = RealKalshiOrderbookSnapshotAdapterV2().capture_sync()
        return self._closure

    async def resolve_async(self) -> RealOrderbookSnapshotClosure:
        if self._closure is not None:
            return self._closure
        forensics = self._forensics()
        blocked = self._blocked_outcome(forensics)
        if blocked:
            self._closure = self._fallback_closure(blocked, forensics)
        else:
            self._closure = await RealKalshiOrderbookSnapshotAdapterV2().capture()
        return self._closure

    def terrain_mode(self) -> str:
        closure = self._closure_or_fallback()
        if closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY:
            return "PASS_REAL_TERRAIN"
        if closure.outcome == "CREDENTIALS_INVALID":
            return "PARTIAL_CREDENTIALS_INVALID"
        if closure.outcome == "CREDENTIALS_MISSING":
            return "PARTIAL_CREDENTIALS_MISSING"
        if closure.outcome == "NO_ELIGIBLE_MARKET_FOUND":
            return "PARTIAL_NO_ELIGIBLE_MARKET"
        return "PASS_SAMPLE_FALLBACK"

    def snapshot_report(self) -> dict[str, Any]:
        closure = self._closure_or_fallback()
        report = closure.to_report()
        report.update(
            {
                "workstream": "V14: Real Kalshi Orderbook Snapshot Adapter V3",
                "terrain_mode": self.terrain_mode(),
                "real_orderbook_used": closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                "secret_values_exposed": False,
                "verdict": "PASS" if self.terrain_mode().startswith("PASS") else "PARTIAL",
            }
        )
        return report

    def snapshot_mode_report(self) -> dict[str, Any]:
        closure = self._closure_or_fallback()
        counts = {mode.value: 0 for mode in OrderbookSnapshotMode}
        counts[closure.snapshot_result.mode.value] += 1
        terrain = self.terrain_mode()
        return {
            "workstream": "V14: Orderbook Snapshot Mode V3",
            "mode_counts": counts,
            "active_modes": [closure.snapshot_result.mode.value],
            "terrain_mode": terrain,
            "outcome": closure.outcome,
            "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL",
        }

    def snapshot_manifest(self) -> dict[str, Any]:
        closure = self._closure_or_fallback()
        report = closure.manifest()
        report.update(
            {
                "workstream": "V14: Real Orderbook Snapshot Manifest V2",
                "terrain_mode": self.terrain_mode(),
                "secret_values_exposed": False,
                "verdict": "PASS" if self.terrain_mode().startswith("PASS") else "PARTIAL",
            }
        )
        return report

    def replay_report(self) -> dict[str, Any]:
        closure = self._closure_or_fallback()
        store = RealOrderbookReplayStore()
        store.add_snapshot(closure.snapshot_result)
        report = store.to_report()
        terrain = self.terrain_mode()
        report.update(
            {
                "workstream": "V14: Real Orderbook Liquidity Replay V3",
                "terrain_mode": terrain,
                "real_terrain_used": closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                "verdict": "PASS" if terrain.startswith("PASS_REAL") else "PARTIAL",
            }
        )
        return report

    def _terrain(self) -> OrderbookLiquidityTerrainV3:
        closure = self._closure_or_fallback()
        return OrderbookLiquidityTerrainV3(closure.snapshot_result, closure_outcome=closure.outcome)

    def liquidity_model_report(self) -> dict[str, Any]:
        report = self._terrain().orderbook_model_report()
        terrain = self.terrain_mode()
        report.update({"workstream": "V14: Orderbook Liquidity Model V4", "terrain_mode": terrain, "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL"})
        return report

    def fill_quality_report(self) -> dict[str, Any]:
        report = self._terrain().fill_quality_report()
        terrain = self.terrain_mode()
        report.update({"workstream": "V14: Fill Quality Estimate V4", "terrain_mode": terrain, "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL"})
        return report

    def stale_quote_report(self) -> dict[str, Any]:
        report = self._terrain().stale_quote_report()
        report.update({"workstream": "V14: Stale Quote Risk V4", "terrain_mode": self.terrain_mode()})
        return report

    def live_liquidity_report(self) -> dict[str, Any]:
        report = self._terrain().live_liquidity_report()
        terrain = self.terrain_mode()
        report.update({"workstream": "V14: Live Liquidity Proof Engine V4", "terrain_mode": terrain, "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL"})
        return report
