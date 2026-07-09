"""Liquidity model reports bound to V16 terrain truth."""

from __future__ import annotations

from typing import Any

from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2
from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2
from predator_mesh.v16.orderbook_snapshot import RealOrderbookSnapshotResultV2
from predator_mesh.v16.terrain_truth import RealTerrainTruthResolution


class LiquidityModelTerrainReporter:
    def __init__(
        self,
        snapshot_result: RealOrderbookSnapshotResultV2 | OrderbookSnapshotResult,
        terrain_truth: RealTerrainTruthResolution,
    ) -> None:
        self.snapshot_result = self._to_v12(snapshot_result)
        self.terrain_truth = terrain_truth
        self.model = OrderbookLiquidityModelV2()

    def _to_v12(self, result: RealOrderbookSnapshotResultV2 | OrderbookSnapshotResult) -> OrderbookSnapshotResult:
        if isinstance(result, OrderbookSnapshotResult):
            return result
        return result.to_orderbook_snapshot_result()

    def _decorate(self, report: dict[str, Any], workstream: str) -> dict[str, Any]:
        fallback_reason = self.snapshot_result.proof.fallback_reason
        report.update(
            {
                "workstream": workstream,
                "terrain_mode": self.snapshot_result.mode.value,
                "terrain_truth_verdict": self.terrain_truth.verdict,
                "source_snapshot_proof_ref": self.snapshot_result.proof.proof_ref,
                "fallback_reason": fallback_reason,
                "secret_values_exposed": False,
                "verdict": "PASS" if self.terrain_truth.verdict.startswith("PASS") else "PARTIAL",
            }
        )
        if self.snapshot_result.mode is not OrderbookSnapshotMode.REAL_READ_ONLY:
            report["verdict"] = "PARTIAL"
        return report

    def orderbook_liquidity_model_report_v6(self) -> dict[str, Any]:
        return self._decorate(self.model.to_report(self.snapshot_result), "V16: Orderbook Liquidity Model V6")

    def fill_quality_estimate_report_v6(self) -> dict[str, Any]:
        return self._decorate(self.model.fill_quality_report_v2(self.snapshot_result), "V16: Fill Quality Estimate V6")

    def stale_quote_risk_report_v6(self) -> dict[str, Any]:
        return self._decorate(self.model.stale_quote_report_v2(), "V16: Stale Quote Risk V6")

    def live_liquidity_proof_engine_report_v6(self) -> dict[str, Any]:
        return self._decorate(LiveLiquidityProofEngineV2().to_report(self.snapshot_result), "V16: Live Liquidity Proof Engine V6")

    def liquidity_execution_feasibility_report_v2(self) -> dict[str, Any]:
        return self._decorate(self.model.execution_feasibility_report(self.snapshot_result), "V16: Liquidity Execution Feasibility V2")
