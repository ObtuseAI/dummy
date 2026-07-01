"""Tests for mesh hybrid model routing."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.output_firewall import ModelOutputFirewall
from model_router.prompt_firewall import PromptFirewallV2
from model_router.router import ModelRouter
from model_router.tasks import ModelTask
from predator_mesh.hybrid_router import HybridModelResult, MeshHybridRouter


class FakeRouter:
    """Deterministic stand-in for ModelRouter in routing tests."""

    def __init__(
        self,
        fast_content: str = '{"dummy_probability":"0.55","confidence_score":"0.72","reasoning":"mock forecast"}',
        critique_content: str = '{"verdict":"proceed","reasoning":"mock critique"}',
        delay: float = 0.0,
        raise_exc: Exception | None = None,
    ) -> None:
        self.fast_content = fast_content
        self.critique_content = critique_content
        self.delay = delay
        self.raise_exc = raise_exc
        self.calls: list[tuple[ModelTask, str]] = []

    async def call(
        self,
        task: ModelTask,
        prompt: str,
        context: dict[str, Any] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> ModelResponseEnvelope:
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.delay:
            await asyncio.sleep(self.delay)
        self.calls.append((task, prompt))
        content = self.fast_content if task == ModelTask.FORECAST_OPINION else self.critique_content
        return ModelResponseEnvelope(
            task=task,
            decision=ModelRouteDecision(
                task=task,
                provider_name="deepseek_v4_flash" if task == ModelTask.FORECAST_OPINION else "minimax_m3",
                model_name="test-model",
                reason="test",
            ),
            prompt=prompt,
            content=content,
            latency_ms=1.0,
        )


@pytest.mark.asyncio
async def test_route_returns_fast_and_critique_envelopes() -> None:
    router = FakeRouter()
    hybrid = MeshHybridRouter(router=router)

    result = await hybrid.route("safe market prompt", timeout=5.0)

    assert not result.degraded
    assert result.fast_envelope is not None
    assert result.critique_envelope is not None
    assert result.fast_envelope["task"] == ModelTask.FORECAST_OPINION.value
    assert result.critique_envelope["task"] == ModelTask.STRATEGY_CRITIQUE.value


@pytest.mark.asyncio
async def test_route_calls_models_concurrently() -> None:
    delay = 0.15
    router = FakeRouter(delay=delay)
    hybrid = MeshHybridRouter(router=router)

    start = time.monotonic()
    result = await hybrid.route("safe market prompt", timeout=5.0)
    elapsed = time.monotonic() - start

    assert not result.degraded
    assert len(router.calls) == 2
    # Concurrent execution should take roughly one delay, not two.
    # Bound is relaxed to avoid flakiness on slower CI runners.
    assert elapsed < 2 * delay


@pytest.mark.asyncio
async def test_prompt_blocked_by_v2_returns_degraded() -> None:
    hybrid = MeshHybridRouter(
        router=FakeRouter(),
        prompt_firewall=PromptFirewallV2(),
    )

    result = await hybrid.route("my secret key is sk-12345678901234567890abc")

    assert result.degraded
    assert result.fallback == "prompt_blocked"
    assert result.blocked_classification == "SECRET_BLOCK"


@pytest.mark.asyncio
async def test_output_firewall_blocks_order_instruction() -> None:
    router = FakeRouter(fast_content="The model says submit a buy order now")
    hybrid = MeshHybridRouter(
        router=router,
        output_firewall=ModelOutputFirewall(),
    )

    result = await hybrid.route("safe market prompt", timeout=5.0)

    assert result.degraded
    assert result.fallback == "output_blocked"
    assert any(b["category"] == "ORDER_INSTRUCTION_BLOCK" for b in result.output_blocked)
    # The blocked fast envelope must be redacted, not the raw model output.
    assert result.fast_envelope is not None
    assert result.fast_envelope.get("blocked") is True
    assert result.fast_envelope.get("block_reason") == "ORDER_INSTRUCTION_BLOCK"
    assert "content" not in result.fast_envelope
    assert "prompt" not in result.fast_envelope
    # The safe critique envelope is still returned normally.
    assert result.critique_envelope is not None
    assert result.critique_envelope.get("blocked") is None
    assert "content" in result.critique_envelope


@pytest.mark.asyncio
async def test_route_timeout_degrades() -> None:
    router = FakeRouter(delay=10.0)
    hybrid = MeshHybridRouter(router=router)

    result = await hybrid.route("safe market prompt", timeout=0.05)

    assert result.degraded
    assert result.fallback == "model_timeout"
