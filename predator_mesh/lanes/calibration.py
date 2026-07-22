"""Forecast/source calibration lane."""

from __future__ import annotations

from typing import Any

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
        forecasts = self.storage.load_all_forecasts_v2()
        settlements = self.storage.load_settlements()

        # Historical mesh fixtures are useful in tests, but they are not real
        # calibration evidence and must never contribute to runtime scores.
        real_forecasts = [
            record
            for record in forecasts
            if not record.market_ticker.upper().startswith("MESH-SYNTH")
            and not record.contract_ticker.upper().startswith("MESH-SYNTH")
            and "synthetic" not in record.forecast_id.lower()
        ]
        real_settlements = [
            record
            for record in settlements
            if not record.market_ticker.upper().startswith("MESH-SYNTH")
            and not record.contract_ticker.upper().startswith("MESH-SYNTH")
            and "synthetic" not in record.source.lower()
        ]

        try:
            dataset = self.spine.score_dataset_v2(real_forecasts, real_settlements)
        except Exception as exc:
            return self._fail(ctx, f"calibration scoring failed: {exc}")

        descriptive_contract_count = int(
            dataset.get("diagnostics", {}).get("scored_contract_count", 0)
        )
        dataset_is_calibratable = dataset.get("status") != "INSUFFICIENT_DATA"
        updates: list[dict[str, Any]] = (
            list(dataset.get("contract_metrics", [])) if dataset_is_calibratable else []
        )

        if ctx.proof_ledger is not None:
            if updates:
                ctx.proof_ledger.record(
                    event="calibration_scored",
                    lane=self.name,
                    settlement_count=descriptive_contract_count,
                    forecast_count=len(real_forecasts),
                    calibration_unit=dataset.get("calibration_unit"),
                    expected_calibration_error=dataset.get("overall", {}).get(
                        "expected_calibration_error"
                    ),
                    maximum_calibration_error=dataset.get("overall", {}).get(
                        "maximum_calibration_error"
                    ),
                )
            else:
                ctx.proof_ledger.record(
                    event="calibration_abstained",
                    lane=self.name,
                    reason=dataset.get("overall", {}).get("reason")
                    or "no_real_scored_forecasts",
                    real_forecast_count=len(real_forecasts),
                    real_settlement_count=len(real_settlements),
                    descriptive_contract_count=descriptive_contract_count,
                )
            ctx.proof_ledger.record(
                event="secret_check_status",
                lane=self.name,
                status="not_performed",
            )

        ctx.shared_state["calibration_updates"] = updates
        ctx.shared_state["calibration_dataset"] = dataset
        if not updates:
            return self._complete(
                ctx,
                {
                    "status": "abstained",
                    "reason": dataset.get("overall", {}).get("reason")
                    or "no_real_scored_forecasts",
                    "calibration_updates": 0,
                    "descriptive_contract_count": descriptive_contract_count,
                    "dataset_metrics": dataset,
                    "updates": [],
                },
                verdict="insufficient_real_calibration_data",
            )
        return self._complete(
            ctx,
            {
                "calibration_updates": len(updates),
                "dataset_metrics": dataset,
                "updates": updates,
            },
            verdict="calibration_scored",
        )
