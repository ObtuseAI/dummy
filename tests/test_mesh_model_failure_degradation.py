"""Tests for mesh model failure degradation."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.tasks import ModelTask
from predator_mesh.budget import build_default_budget
from predator_mesh.hybrid_router import HybridModelResult, MeshHybridRouter
from predator_mesh.lanes.forecast_update import (
    ForecastUpdateLane,
    _synthetic_forecast,
    _synthetic_orderbook,
)
from predator_mesh.models import LaneState, MeshBudget, MeshContext, MeshTimeout


class BadRouter:
    """Always raises, simulating a total provider failure."""

    async def call(self, *args: Any, **kwargs: Any) -> ModelResponseEnvelope:
        raise RuntimeError("provider down")


class FailingHybridRouter(MeshHybridRouter):
    """Returns a degraded result deterministically."""

    async def route(self, *args: Any, **kwargs: Any) -> HybridModelResult:
        return HybridModelResult(
            degraded=True,
            fallback="injected_degraded",
            prompt_sanitized="safe",
        )


class SlowHybridRouter(MeshHybridRouter):
    """Hangs longer than the per-lane timeout."""

    async def route(self, *args: Any, **kwargs: Any) -> HybridModelResult:
        await asyncio.sleep(10.0)
        return HybridModelResult(degraded=True, fallback="slow")


@pytest.mark.asyncio
async def test_router_exception_degrades() -> None:
    hybrid = MeshHybridRouter(router=BadRouter())

    result = await hybrid.route("safe market prompt", timeout=5.0)

    assert result.degraded
    assert result.fallback.startswith("model_error:")
    assert "RuntimeError" in result.fallback


@pytest.mark.asyncio
async def test_forecast_lane_degraded_on_model_failure() -> None:
    forecast = _synthetic_forecast()
    lane = ForecastUpdateLane(
        hybrid_router=FailingHybridRouter(),
        base_forecast=forecast,
        orderbook=_synthetic_orderbook(forecast.market_ticker, forecast.contract_ticker),
    )
    budget = build_default_budget()
    ctx = MeshContext(
        run_id="failure-test",
        lane_name=lane.name,
        budget=budget,
        timeout=MeshTimeout(per_lane_timeout_s=5.0),
        proof_ledger=None,
    )

    result = await lane.execute(ctx)

    assert result.lane_name == lane.name
    assert result.state == LaneState.DEGRADED
    assert "hybrid model degraded" in result.error


@pytest.mark.asyncio
async def test_forecast_lane_blocked_when_budget_exhausted() -> None:
    forecast = _synthetic_forecast()
    lane = ForecastUpdateLane(
        base_forecast=forecast,
        orderbook=_synthetic_orderbook(forecast.market_ticker, forecast.contract_ticker),
    )
    budget = MeshBudget(max_provider_calls=0, max_kalshi_calls=0)
    ctx = MeshContext(
        run_id="budget-test",
        lane_name=lane.name,
        budget=budget,
        timeout=MeshTimeout(per_lane_timeout_s=5.0),
        proof_ledger=None,
    )

    result = await lane.execute(ctx)

    assert result.state == LaneState.BLOCKED
    assert "provider budget exhausted" in result.error


class SlowInternalRouter:
    """Sleeps long enough that MeshHybridRouter's wait_for times out."""

    async def call(self, *args: Any, **kwargs: Any) -> ModelResponseEnvelope:
        await asyncio.sleep(0.5)
        return ModelResponseEnvelope(
            task=ModelTask.FORECAST_OPINION,
            decision=ModelRouteDecision(
                task=ModelTask.FORECAST_OPINION,
                provider_name="mock",
                model_name="mock",
                reason="test",
            ),
            prompt="safe",
            content='{"dummy_probability":"0.5","confidence_score":"0.5","reasoning":"x"}',
            latency_ms=1.0,
        )


@pytest.mark.asyncio
async def test_forecast_lane_times_out_on_hanging_router() -> None:
    forecast = _synthetic_forecast()
    lane = ForecastUpdateLane(
        hybrid_router=MeshHybridRouter(router=SlowInternalRouter()),
        base_forecast=forecast,
        orderbook=_synthetic_orderbook(forecast.market_ticker, forecast.contract_ticker),
    )
    budget = build_default_budget()
    ctx = MeshContext(
        run_id="timeout-test",
        lane_name=lane.name,
        budget=budget,
        timeout=MeshTimeout(per_lane_timeout_s=0.05),
        proof_ledger=None,
    )

    result = await lane.execute(ctx)

    # MeshHybridRouter turns its own timeout into a degraded result.
    assert result.state == LaneState.DEGRADED
    assert "model_timeout" in result.error


@pytest.mark.asyncio
async def test_forecast_lane_success_consumes_provider_budget() -> None:
    """A successful hybrid forecast pair consumes exactly two provider calls."""
    from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision

    class CountingRouter:
        def __init__(self) -> None:
            self.call_count = 0

        async def call(
            self,
            task: ModelTask,
            prompt: str,
            context: dict[str, Any] | None = None,
            max_tokens: int = 512,
            temperature: float = 0.2,
        ) -> ModelResponseEnvelope:
            self.call_count += 1
            content = (
                '{"dummy_probability":"0.55","confidence_score":"0.72","reasoning":"x"}'
                if task == ModelTask.FORECAST_OPINION
                else '{"verdict":"proceed","reasoning":"x"}'
            )
            return ModelResponseEnvelope(
                task=task,
                decision=ModelRouteDecision(
                    task=task,
                    provider_name=(
                        "gemini_3_6_flash"
                        if task == ModelTask.FORECAST_OPINION
                        else "claude_sonnet_5"
                    ),
                    model_name="test-model",
                    reason="test",
                ),
                prompt=prompt,
                content=content,
                latency_ms=1.0,
            )

    router = CountingRouter()
    forecast = _synthetic_forecast()
    lane = ForecastUpdateLane(
        hybrid_router=MeshHybridRouter(router=router),
        base_forecast=forecast,
        orderbook=_synthetic_orderbook(forecast.market_ticker, forecast.contract_ticker),
    )
    budget = build_default_budget()
    ctx = MeshContext(
        run_id="budget-test",
        lane_name=lane.name,
        budget=budget,
        timeout=MeshTimeout(per_lane_timeout_s=5.0),
        proof_ledger=None,
    )

    result = await lane.execute(ctx)

    assert result.state == LaneState.COMPLETED
    assert router.call_count == 2
    assert budget.provider_call_count == 2
