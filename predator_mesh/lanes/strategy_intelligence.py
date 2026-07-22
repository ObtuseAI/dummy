"""Strategy intelligence lane."""

from __future__ import annotations

from typing import Any

from core.ontology import Forecast, OrderBook
from strategies.critique import StrategyCritiqueEngine
from strategies.intelligence import StrategyIntelligence
from strategies.scan import StrategyScanner
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)

class StrategyIntelligenceLane(BaseLane):
    """Invoke strategy families through the existing StrategyIntelligence engine.

    By default the lane uses an empty strategy scanner so that unit tests stay
    fast and deterministic.  A real scanner (or a populated
    :class:`StrategyIntelligence`) can be injected for live mesh runs.
    """

    name = "strategy_intelligence"
    dependencies = ("forecast_update",)
    priority = MeshPriority(level=LanePriority.STRATEGY_REVIEW)
    timeout = MeshTimeout(per_lane_timeout_s=12.0)

    def __init__(
        self,
        intelligence: StrategyIntelligence | None = None,
        forecast: Forecast | None = None,
        orderbook: OrderBook | None = None,
    ) -> None:
        self.intelligence = intelligence or StrategyIntelligence(
            scanner=StrategyScanner(strategies=[]),
            critique_engine=StrategyCritiqueEngine(),
        )
        self.forecast = forecast
        self.orderbook = orderbook

    async def execute(self, ctx: MeshContext) -> MeshResult:
        forecast = self.forecast or ctx.shared_state.get("base_forecast")
        orderbook = self.orderbook or ctx.shared_state.get("orderbook")
        has_real_inputs = (
            forecast is not None
            and orderbook is not None
            and not forecast.market_ticker.upper().startswith("MESH-SYNTH")
            and not forecast.contract_ticker.upper().startswith("MESH-SYNTH")
            and not orderbook.market_ticker.upper().startswith("MESH-SYNTH")
            and not orderbook.contract_ticker.upper().startswith("MESH-SYNTH")
        )
        if not has_real_inputs:
            if ctx.proof_ledger is not None:
                ctx.proof_ledger.record(
                    event="strategy_abstained",
                    lane=self.name,
                    reason="no_real_strategy_input",
                )
                ctx.proof_ledger.record(
                    event="secret_check_status",
                    lane=self.name,
                    status="not_performed",
                )
            ctx.shared_state["strategy_intelligence_results"] = []
            return self._complete(
                ctx,
                {"status": "abstained", "reason": "no_real_strategy_input", "strategies": []},
                verdict="no_real_strategy_input",
            )

        try:
            assert forecast is not None and orderbook is not None
            results = await self.intelligence.evaluate(forecast, orderbook)
        except Exception as exc:
            return self._fail(ctx, f"strategy intelligence failed: {exc}")

        payload: list[dict[str, Any]] = []
        if ctx.proof_ledger is not None:
            for result in results:
                ctx.proof_ledger.record(
                    event="strategy_evaluated",
                    lane=self.name,
                    family=result.scan_result.family,
                    market_ticker=result.scan_result.market_ticker,
                    contract_ticker=result.scan_result.contract_ticker,
                    has_draft=result.draft is not None,
                    no_trade_reason=(
                        result.no_trade_reason.reason if result.no_trade_reason else None
                    ),
                    critique_verdict=(
                        result.critique.verdict if result.critique else None
                    ),
                )
            ctx.proof_ledger.record(
                event="secret_check_status",
                lane=self.name,
                status="not_performed",
            )
        for result in results:
            payload.append(
                {
                    "family": result.scan_result.family,
                    "market_ticker": result.scan_result.market_ticker,
                    "contract_ticker": result.scan_result.contract_ticker,
                    "edge_estimate": result.scan_result.edge_estimate,
                    "has_draft": result.draft is not None,
                    "draft_side": result.draft.side if result.draft else None,
                    "no_trade_reason": (
                        result.no_trade_reason.reason if result.no_trade_reason else None
                    ),
                    "critique_verdict": (
                        result.critique.verdict if result.critique else None
                    ),
                }
            )

        ctx.shared_state["strategy_intelligence_results"] = results
        if not results:
            if ctx.proof_ledger is not None:
                ctx.proof_ledger.record(
                    event="strategy_abstained",
                    lane=self.name,
                    reason="no_strategy_results",
                )
            return self._complete(
                ctx,
                {"status": "abstained", "reason": "no_strategy_results", "strategies": []},
                verdict="no_strategy_results",
            )
        return self._complete(ctx, {"strategies": payload}, verdict="strategies_evaluated")
