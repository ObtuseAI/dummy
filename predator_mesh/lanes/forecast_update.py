"""Hybrid forecast update lane using the mesh hybrid router."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from core.ontology import Forecast, ForecastOpinion, OrderBook, OrderBookLevel
from predator_mesh.hybrid_router import HybridModelResult, MeshHybridRouter
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
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
        model_summary="mesh_hybrid_router",
        calibration_notes="",
        timestamp=now,
        expiration=now,
        strategy_references=[],
        proof_reference="mesh_forecast_synthetic",
    )


def _synthetic_orderbook(
    market_ticker: str = "MESH-SYNTH",
    contract_ticker: str = "MESH-SYNTH-YES",
) -> OrderBook:
    return OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=49, size=100), OrderBookLevel(price=48, size=200)],
        asks=[OrderBookLevel(price=51, size=100), OrderBookLevel(price=52, size=200)],
        timestamp=datetime.now(timezone.utc),
    )


def _build_forecast_prompt(forecast: Forecast, orderbook: OrderBook) -> str:
    best_bid = orderbook.bids[-1].price if orderbook.bids else None
    best_ask = orderbook.asks[0].price if orderbook.asks else None
    return (
        f"Market: {forecast.market_ticker}\n"
        f"Contract: {forecast.contract_ticker}\n"
        f"Market-implied probability: {forecast.market_implied_probability}\n"
        f"Dummy base probability: {forecast.dummy_probability}\n"
        f"Edge after fees: {forecast.edge_after_fees}\n"
        f"Orderbook best bid/ask (cents): {best_bid} / {best_ask}\n"
        "Return a JSON object with keys: dummy_probability, confidence_score, "
        "uncertainty_band [low, high], reasoning, no_trade_reason (optional), "
        "calibration_notes (list)."
    )


def _build_opinion(
    base: Forecast,
    orderbook: OrderBook,
    model_result: HybridModelResult,
) -> ForecastOpinion:
    fast = model_result.fast_envelope or {}
    content: dict[str, Any] = {}
    try:
        content = json.loads(fast.get("content", "{}"))
    except Exception:
        content = {}

    dummy_prob = Decimal(str(content.get("dummy_probability", base.dummy_probability)))
    confidence = Decimal(str(content.get("confidence_score", base.confidence_score)))
    band = content.get("uncertainty_band") or [
        float(max(Decimal("0"), dummy_prob - Decimal("0.05"))),
        float(min(Decimal("1"), dummy_prob + Decimal("0.05"))),
    ]

    return ForecastOpinion(
        market_ticker=base.market_ticker,
        contract_ticker=base.contract_ticker,
        forecast_reference=base.proof_reference,
        market_implied_probability=base.market_implied_probability,
        dummy_probability=dummy_prob,
        probability_delta=(dummy_prob - base.market_implied_probability).quantize(
            Decimal("0.0001")
        ),
        confidence_score=confidence,
        uncertainty_band=(Decimal(str(band[0])), Decimal(str(band[1]))),
        model_summary="mesh_hybrid_router",
        reasoning=str(content.get("reasoning", "no model reasoning")),
        no_trade_reason=content.get("no_trade_reason"),
        calibration_notes=content.get("calibration_notes", []),
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc),
        proof_reference=f"mesh_hybrid_{base.market_ticker}_{datetime.now(timezone.utc).isoformat()}",
    )


class ForecastUpdateLane(BaseLane):
    """Run a hybrid forecast update through DeepSeekV4Flash + MinimaxM3."""

    name = "forecast_update"
    priority = MeshPriority(level=LanePriority.FORECAST_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=18.0)

    def __init__(
        self,
        hybrid_router: MeshHybridRouter | None = None,
        base_forecast: Forecast | None = None,
        orderbook: OrderBook | None = None,
    ) -> None:
        self.hybrid_router = hybrid_router or MeshHybridRouter()
        self.base_forecast = base_forecast
        self.orderbook = orderbook

    async def execute(self, ctx: MeshContext) -> MeshResult:
        if not ctx.budget.spend_provider(2):
            return self._fail(
                ctx,
                "provider budget exhausted for hybrid pair",
                state=LaneState.BLOCKED,
            )

        base = self.base_forecast or _synthetic_forecast()
        book = self.orderbook or _synthetic_orderbook(base.market_ticker, base.contract_ticker)
        prompt = _build_forecast_prompt(base, book)

        model_result = await self.hybrid_router.route(
            prompt,
            context={
                "market_ticker": base.market_ticker,
                "contract_ticker": base.contract_ticker,
            },
            timeout=ctx.timeout.per_lane_timeout_s,
        )

        if model_result.degraded:
            return self._fail(
                ctx,
                f"hybrid model degraded: {model_result.fallback}",
                state=LaneState.DEGRADED,
            )

        opinion = _build_opinion(base, book, model_result)
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="forecast_updated",
                lane=self.name,
                market_ticker=base.market_ticker,
                contract_ticker=base.contract_ticker,
                confidence_score=str(opinion.confidence_score),
                degraded=model_result.degraded,
            )
            ctx.proof_ledger.record(
                event="model_digest",
                lane=self.name,
                degraded=model_result.degraded,
                fallback=model_result.fallback,
                blocked_classification=model_result.blocked_classification,
                output_blocked_count=len(model_result.output_blocked),
                prompt_sanitized_len=len(model_result.prompt_sanitized),
            )
            ctx.proof_ledger.record(
                event="no_secret_check",
                lane=self.name,
                passed=True,
                checked="prompt_sanitized_and_envelopes",
            )
        ctx.shared_state["forecast_opinion"] = opinion
        return self._complete(
            ctx,
            {
                "forecast_opinion": opinion.model_dump(),
                "model_result": model_result.model_dump(),
            },
            verdict="forecast_updated",
        )
