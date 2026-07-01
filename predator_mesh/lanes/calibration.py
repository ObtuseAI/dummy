"""Forecast/source calibration lane."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from calibration.schema import ForecastRecordV2, SettlementRecord
from calibration.spine import CalibrationSpine
from calibration.storage import CalibrationStorage
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class CalibrationLane(BaseLane):
    """Track forecast/source quality using the existing calibration spine."""

    name = "calibration"
    priority = MeshPriority(level=LanePriority.CALIBRATION_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    def __init__(
        self,
        spine: CalibrationSpine | None = None,
        storage: CalibrationStorage | None = None,
    ) -> None:
        self.spine = spine or CalibrationSpine()
        self.storage = storage or CalibrationStorage()

    async def execute(self, ctx: MeshContext) -> MeshResult:
        updates: list[dict[str, Any]] = []

        # Score any persisted V2 forecasts for the synthetic contract.
        contract = "MESH-SYNTH-YES"
        forecasts = self.storage.load_forecasts_v2(contract)

        # If none exist, create a single synthetic record so the spine always
        # has something to score in a fresh environment.
        if not forecasts:
            now = datetime.now(timezone.utc)
            forecasts = [
                ForecastRecordV2(
                    forecast_id="mesh-calibration-synthetic",
                    market_ticker="MESH-SYNTH",
                    contract_ticker=contract,
                    model_route="mesh_hybrid_router",
                    market_implied_probability=Decimal("0.5000"),
                    dummy_probability=Decimal("0.5200"),
                    deepseekv4flash_probability=Decimal("0.5300"),
                    minimaxm3_probability=Decimal("0.5100"),
                    final_probability=Decimal("0.5200"),
                    confidence_bucket="medium",
                    timestamp=now,
                    settlement_status="settled",
                    realized_outcome=1,
                    no_trade_reason=None,
                )
            ]

        settlement = SettlementRecord(
            market_ticker="MESH-SYNTH",
            contract_ticker=contract,
            outcome=1,
            settled_at=datetime.now(timezone.utc),
            source="mesh_synthetic",
        )

        try:
            metrics = self.spine.score_v2(forecasts, settlement)
            updates.append(metrics.model_dump())
        except Exception as exc:
            return self._fail(ctx, f"calibration scoring failed: {exc}")

        ctx.shared_state["calibration_updates"] = updates
        return self._complete(
            ctx,
            {"calibration_updates": len(updates), "updates": updates},
            verdict="calibration_scored",
        )
