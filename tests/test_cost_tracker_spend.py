"""CostTracker aggregates real per-provider spend, not just call counts."""
from __future__ import annotations

from model_router.cost_tracker import CostTracker
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.tasks import ModelTask


def _envelope(provider: str, latency_ms: float, cost_usd=None) -> ModelResponseEnvelope:
    metadata = {"provider": provider}
    if cost_usd is not None:
        metadata["cost_usd"] = cost_usd
    return ModelResponseEnvelope(
        task=ModelTask.FORECAST_OPINION,
        decision=ModelRouteDecision(
            task=ModelTask.FORECAST_OPINION,
            provider_name=provider,
            model_name=f"vendor/{provider}",
            reason="test",
        ),
        prompt="p",
        content="c",
        raw_metadata=metadata,
        latency_ms=latency_ms,
    )


def test_costs_aggregate_per_provider_and_in_total():
    tracker = CostTracker()
    tracker.record(_envelope("glm_5_2", 100.0, cost_usd=0.001))
    tracker.record(_envelope("glm_5_2", 300.0, cost_usd=0.002))
    tracker.record(_envelope("claude_sonnet_5", 500.0, cost_usd=0.01))

    summary = tracker.summary()
    assert summary["calls"] == 3
    assert summary["total_cost_usd"] == 0.013
    assert summary["uncosted_calls"] == 0
    assert summary["by_provider"]["glm_5_2"]["calls"] == 2
    assert summary["by_provider"]["glm_5_2"]["cost_usd"] == 0.003
    assert summary["by_provider"]["claude_sonnet_5"]["cost_usd"] == 0.01


def test_missing_or_invalid_cost_is_disclosed_not_zeroed():
    tracker = CostTracker()
    tracker.record(_envelope("mock", 10.0))
    tracker.record(_envelope("mock", 10.0, cost_usd="bogus"))
    tracker.record(_envelope("mock", 10.0, cost_usd=-1.0))

    summary = tracker.summary()
    assert summary["total_cost_usd"] == 0.0
    assert summary["uncosted_calls"] == 3
    assert summary["by_provider"]["mock"]["uncosted_calls"] == 3


def test_legacy_summary_keys_remain():
    tracker = CostTracker()
    tracker.record(_envelope("mock", 250.0, cost_usd=0.0))
    summary = tracker.summary()
    for key in ("calls", "total_latency_ms", "avg_latency_ms"):
        assert key in summary
    assert summary["avg_latency_ms"] == 250.0
