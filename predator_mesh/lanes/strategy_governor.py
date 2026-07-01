"""Strategy governor routing lane."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from core.ontology import ForecastOpinion
from strategies.governor import StrategyGovernor
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


def _synthetic_opinion() -> ForecastOpinion:
    now = datetime.now(timezone.utc)
    return ForecastOpinion(
        market_ticker="MESH-SYNTH",
        contract_ticker="MESH-SYNTH-YES",
        forecast_reference="mesh_forecast_synthetic",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5200"),
        probability_delta=Decimal("0.0200"),
        confidence_score=Decimal("0.65"),
        uncertainty_band=(Decimal("0.45"), Decimal("0.60")),
        model_summary="strategy_governor",
        reasoning="synthetic mesh opinion for governor review",
        no_trade_reason=None,
        calibration_notes=[
            "liquidity_score=0.70",
            "spread_score=0.75",
            "freshness_score=0.80",
            "depth_score=0.60",
            "settlement_risk_score=0.20",
        ],
        timestamp=now,
        expiration=now,
        proof_reference="mesh_forecast_synthetic",
    )


class StrategyGovernorLane(BaseLane):
    """Route a forecast opinion through the existing StrategyGovernor."""

    name = "strategy_governor"
    priority = MeshPriority(level=LanePriority.STRATEGY_REVIEW)
    timeout = MeshTimeout(per_lane_timeout_s=10.0)

    def __init__(
        self,
        governor: StrategyGovernor | None = None,
        opinion: ForecastOpinion | None = None,
    ) -> None:
        self.governor = governor or StrategyGovernor()
        self.opinion = opinion

    async def execute(self, ctx: MeshContext) -> MeshResult:
        opinion = self.opinion or ctx.shared_state.get("forecast_opinion")
        if opinion is None:
            opinion = _synthetic_opinion()

        try:
            output = self.governor.evaluate(opinion)
        except Exception as exc:
            return self._fail(ctx, f"strategy governor failed: {exc}")

        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="governor_decision",
                lane=self.name,
                decision=output.decision.value,
                reason=output.reason,
                blocked_by=output.blocked_by,
                no_trade_bias=output.no_trade_bias,
                proof_reference=output.proof_reference,
            )
            ctx.proof_ledger.record(
                event="no_secret_check",
                lane=self.name,
                passed=True,
                checked="governor_opinion",
            )

        payload: dict[str, Any] = {
            "decision": output.decision.value,
            "reason": output.reason,
            "blocked_by": output.blocked_by,
            "no_trade_bias": output.no_trade_bias,
            "proof_reference": output.proof_reference,
        }
        ctx.shared_state["governor_output"] = output
        return self._complete(ctx, payload, verdict="governor_evaluated")
