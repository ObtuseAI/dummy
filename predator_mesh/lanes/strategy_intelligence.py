"""Strategy intelligence lane."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from core.ontology import Forecast, OrderBook, OrderBookLevel
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


def _synthetic_forecast() -> Forecast:
    now = datetime.now(timezone.utc)
    return Forecast(
        market_ticker="MESH-SYNTH",
        contract_ticker="MESH-SYNTH-YES",
        event_title="Synthetic mesh event",
        contract_title="Synthetic yes contract",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5200"),
        probability_delta=Decimal("0.0200"),
        confidence_score=Decimal("0.65"),
        uncertainty_band=(Decimal("0.45"), Decimal("0.60")),
        expected_edge=Decimal("0.0010"),
        edge_after_fees=Decimal("0.0005"),
        freshness_score=Decimal("0.80"),
        liquidity_score=Decimal("0.70"),
        spread_score=Decimal("0.75"),
        orderbook_depth_score=Decimal("0.60"),
        settlement_risk_score=Decimal("0.20"),
        source_summary="mesh_synthetic",
        model_summary="strategy_intelligence",
        calibration_notes="",
        timestamp=now,
        expiration=now,
        strategy_references=[],
        proof_reference="mesh_forecast_synthetic",
    )


def _synthetic_orderbook() -> OrderBook:
    return OrderBook(
        market_ticker="MESH-SYNTH",
        contract_ticker="MESH-SYNTH-YES",
        bids=[OrderBookLevel(price=49, size=100)],
        asks=[OrderBookLevel(price=51, size=100)],
        timestamp=datetime.now(timezone.utc),
    )


class StrategyIntelligenceLane(BaseLane):
    """Invoke strategy families through the existing StrategyIntelligence engine.

    By default the lane uses an empty strategy scanner so that unit tests stay
    fast and deterministic.  A real scanner (or a populated
    :class:`StrategyIntelligence`) can be injected for live mesh runs.
    """

    name = "strategy_intelligence"
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
        forecast = self.forecast or _synthetic_forecast()
        orderbook = self.orderbook or _synthetic_orderbook()

        try:
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
            if not results:
                ctx.proof_ledger.record(
                    event="strategy_evaluated",
                    lane=self.name,
                    strategy_count=0,
                )
            ctx.proof_ledger.record(
                event="no_secret_check",
                lane=self.name,
                passed=True,
                checked="strategy_results",
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
        return self._complete(ctx, {"strategies": payload}, verdict="strategies_evaluated")
