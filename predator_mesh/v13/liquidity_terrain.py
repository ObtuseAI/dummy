"""V13 liquidity-model reports with real-terrain verdicts."""

from __future__ import annotations

from typing import Any

from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2
from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


class OrderbookLiquidityTerrainV3:
    def __init__(self, result: OrderbookSnapshotResult | None = None, *, closure_outcome: str = "") -> None:
        self.model = OrderbookLiquidityModelV2()
        self.result = result or self.model.fallback_result()
        self.closure_outcome = closure_outcome

    def terrain_verdict(self) -> str:
        if self.result.mode is OrderbookSnapshotMode.REAL_READ_ONLY:
            return "PASS_REAL_TERRAIN"
        if self.result.mode is OrderbookSnapshotMode.SAMPLE_STATIC_FALLBACK:
            if self.closure_outcome == "CREDENTIALS_MISSING":
                return "PARTIAL_CREDENTIALS_MISSING"
            if self.closure_outcome == "NO_ELIGIBLE_MARKET_FOUND":
                return "PARTIAL_NO_ELIGIBLE_MARKET"
            return "PASS_SAMPLE_FALLBACK"
        return "FAIL_MALFORMED_PIPELINE"

    def orderbook_model_report(self) -> dict[str, Any]:
        base = self.model.to_report(self.result)
        terrain = self.terrain_verdict()
        base.update(
            {
                "workstream": "V13: Orderbook Liquidity Model V3",
                "terrain_verdict": terrain,
                "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL",
            }
        )
        return base

    def fill_quality_report(self) -> dict[str, Any]:
        base = self.model.fill_quality_report_v2(self.result)
        terrain = self.terrain_verdict()
        base.update(
            {
                "workstream": "V13: Fill Quality Estimate V3",
                "terrain_verdict": terrain,
                "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL",
            }
        )
        return base

    def stale_quote_report(self) -> dict[str, Any]:
        base = self.model.stale_quote_report_v2()
        base.update(
            {
                "workstream": "V13: Stale Quote Risk V3",
                "terrain_verdict": self.terrain_verdict(),
            }
        )
        return base

    def live_liquidity_report(self) -> dict[str, Any]:
        base = LiveLiquidityProofEngineV2().to_report(self.result)
        terrain = self.terrain_verdict()
        base.update(
            {
                "workstream": "V13: Live Liquidity Proof Engine V3",
                "terrain_verdict": terrain,
                "verdict": "PASS" if terrain.startswith("PASS") else "PARTIAL",
            }
        )
        return base
