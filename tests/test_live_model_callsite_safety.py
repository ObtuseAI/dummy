from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from autonomy.brain import (
    DEBATE_HARD_MAX_MARKETS_PER_CYCLE,
    _conservative_debate_panel_cost_usd,
    _debate_max_logical_calls_per_cycle,
    _debate_max_usd_per_cycle,
    _debate_top_k,
)
from autonomy.loss_engine import MAX_NARRATION_SCOPES_PER_RUN, narrate_losses
from autonomy.session import _background_debate_live_enabled
from calibration.storage import CalibrationStorage
from forecasting.real_market_loop import (
    MODEL_MODE_DEGRADED_QUANT_ONLY,
    RealMarketForecastLoopV2,
)
from model_router.config import ModelRoutingConfig, load_model_routing_config
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision


def test_live_model_config_rejects_string_booleans() -> None:
    with pytest.raises(ValidationError):
        ModelRoutingConfig(live_model_calls_enabled="true")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("config_enabled", "runtime_flag", "expected"),
    [
        (False, None, False),
        (False, "1", False),
        (True, None, False),
        (True, "0", False),
        (True, "1", True),
    ],
)
def test_background_debate_is_a_two_key_gate(
    monkeypatch,
    config_enabled: bool,
    runtime_flag: str | None,
    expected: bool,
) -> None:
    if runtime_flag is None:
        monkeypatch.delenv("DUMMY_DEBATE_LIVE", raising=False)
    else:
        monkeypatch.setenv("DUMMY_DEBATE_LIVE", runtime_flag)
    assert _background_debate_live_enabled(config_enabled) is expected


def test_persistent_top_k_is_hard_clamped_and_invalid_budgets_close(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "10")
    assert _debate_top_k() == DEBATE_HARD_MAX_MARKETS_PER_CYCLE

    monkeypatch.setenv("DUMMY_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE", "not-an-int")
    monkeypatch.setenv("DUMMY_DEBATE_MAX_USD_PER_CYCLE", "NaN")
    assert _debate_max_logical_calls_per_cycle() == 0
    assert _debate_max_usd_per_cycle() == 0.0


def test_exact_panel_has_a_finite_conservative_cost_preflight() -> None:
    config = load_model_routing_config()
    cost = _conservative_debate_panel_cost_usd(SimpleNamespace(config=config))
    assert 0 < cost <= 0.10


def test_loss_narration_has_a_hard_scope_call_cap() -> None:
    class Router:
        def __init__(self) -> None:
            self.calls = 0

        async def call(self, task, prompt, context=None):
            self.calls += 1
            return ModelResponseEnvelope(
                task=task,
                decision=ModelRouteDecision(
                    task=task,
                    provider_name="glm_5_2",
                    model_name="z-ai/glm-5.2",
                    reason="test",
                ),
                prompt=prompt,
                content=json.dumps({"note": "bounded research commentary"}),
                latency_ms=1.0,
            )

    router = Router()
    attribution = {
        "scopes": [
            {
                "scope": f"scope-{index}",
                "verdict": "bleeding",
                "cluster_edge": -0.1,
                "worst_buckets": [],
            }
            for index in range(MAX_NARRATION_SCOPES_PER_RUN + 4)
        ]
    }
    result = narrate_losses(attribution, router)
    assert len(result) == MAX_NARRATION_SCOPES_PER_RUN
    assert router.calls == MAX_NARRATION_SCOPES_PER_RUN


@pytest.mark.asyncio
async def test_v2_stops_after_first_invalid_live_panel(monkeypatch, tmp_path) -> None:
    config = load_model_routing_config().model_copy(
        update={"live_model_calls_enabled": True}
    )

    class Engine:
        def __init__(self) -> None:
            self.calls = 0
            self.router = SimpleNamespace(
                config=config,
                providers={
                    name: SimpleNamespace(available=True)
                    for name in config.hybrid_providers
                },
            )

        async def hybrid_review(self, **_kwargs):
            self.calls += 1
            return None

    class Reader:
        async def close(self) -> None:
            return None

        def endpoints_called(self):
            return []

        def order_creating_endpoints_called(self):
            return []

    engine = Engine()
    loop = RealMarketForecastLoopV2(
        hybrid_engine=engine,
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
        model_authority_path=tmp_path / "missing-authority.json",
        model_authority_approved_roots=[tmp_path],
    )

    async def fake_fetch(_reader, max_markets):
        entries = []
        for market, contract, orderbook in loop._mock_market_data():
            scores = loop._score_market(market, contract, orderbook)
            if scores is not None:
                entries.append((market, contract, orderbook, scores))
        return entries[:max_markets]

    import forecasting.real_market_loop as loop_module

    monkeypatch.setattr(loop_module, "KalshiRealReadOnly", Reader)
    monkeypatch.setattr(loop, "_fetch_live_market_data", fake_fetch)

    result = await loop.run(max_markets=3)
    assert engine.calls == 1
    assert result["model_mode"] == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert any("review_not_mapping" in reason for reason in result["model_degradation_reasons"])
