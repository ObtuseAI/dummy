import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from calibration.storage import CalibrationStorage
from forecasting.hybrid_engine import HybridForecastEngine
from forecasting.model_probability_authority import (
    EXPECTED_PROVIDER_MODELS,
    MODEL_AUTHORITY_SCHEMA,
    MODEL_EVIDENCE_MODE,
    MODEL_EVIDENCE_SCHEMA,
    model_probability_scope,
)
from execution.hybrid_path import _RealMarketForecastLoopV2WithDetails
from forecasting.real_market_loop import (
    MODEL_MODE_DEGRADED_QUANT_ONLY,
    MODEL_MODE_LIVE_HYBRID,
    MODEL_MODE_MOCK_ONLY,
    REVIEW_ROUTE_CONTRACTS,
    RealMarketForecastLoopV2,
)
from model_router.config import ModelRoutingConfig, ProviderConfig
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.router import ModelRouter


def _routing_config(*, live_enabled: bool = True) -> ModelRoutingConfig:
    return ModelRoutingConfig(
        default_provider={
            **{
                task.value: provider_name
                for task, provider_name, _model_name in REVIEW_ROUTE_CONTRACTS.values()
            },
            "trade_draft": "gpt_5_6_luna",
            "hybrid_review": "hybrid",
        },
        hybrid_providers=[
            "gemini_3_6_flash",
            "gpt_5_6_luna",
            "claude_sonnet_5",
            "glm_5_2",
        ],
        provider_configs={
            "gemini_3_6_flash": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="google/gemini-3.6-flash",
                route_mode="openrouter",
            ),
            "gpt_5_6_luna": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="openai/gpt-5.6-luna",
                route_mode="openrouter",
            ),
            "claude_sonnet_5": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="anthropic/claude-sonnet-5",
                route_mode="openrouter",
            ),
            "glm_5_2": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="z-ai/glm-5.2",
                route_mode="openrouter",
            ),
        },
        live_model_calls_enabled=live_enabled,
    )


def _write_config(tmp_path, config: ModelRoutingConfig):
    path = tmp_path / "routing.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    return path


def _payload(review_key: str) -> dict:
    if review_key == "primary_forecast":
        return {
            "dummy_probability": "0.91",
            "confidence_score": "0.88",
            "uncertainty_band": ["0.80", "0.95"],
            "reasoning": "forecast",
            "evidence_used": ["supplied orderbook"],
        }
    if review_key == "rapid_forecast":
        return {
            "dummy_probability": "0.89",
            "confidence_score": "0.84",
            "uncertainty_band": ["0.79", "0.94"],
            "reasoning": "independent rapid forecast",
            "action": "consider_yes",
            "entry_condition": "ask remains at or below 51 cents",
        }
    if review_key == "no_trade":
        return {"reason": None, "contributing_factors": []}
    if review_key == "critique":
        return {"verdict": "proceed", "reasoning": "critique"}
    if review_key == "risk":
        return {"risk_level": "low", "reasoning": "risk"}
    if review_key == "thesis":
        return {"thesis": "thesis", "confidence": 0.8}
    return {"note": "base rate appears appropriately calibrated"}


def _valid_reviews() -> dict[str, ModelResponseEnvelope]:
    reviews: dict[str, ModelResponseEnvelope] = {}
    for review_key, (task, provider_name, model_name) in REVIEW_ROUTE_CONTRACTS.items():
        reviews[review_key] = ModelResponseEnvelope(
            task=task,
            decision=ModelRouteDecision(
                task=task,
                provider_name=provider_name,
                model_name=model_name,
                reason="task default provider",
            ),
            prompt="test",
            content=json.dumps(_payload(review_key)),
            raw_metadata={
                "provider": "openrouter_generic",
                "model": model_name,
                "error_class": None,
            },
            latency_ms=1.0,
        )
    return reviews


class _FakeHybridEngine:
    def __init__(
        self,
        *,
        live_enabled: bool = True,
        bad_call: int | None = None,
        failure_kind: str | None = None,
    ):
        self.router = SimpleNamespace(
            config=_routing_config(live_enabled=live_enabled),
            providers={
                "gemini_3_6_flash": SimpleNamespace(available=True),
                "gpt_5_6_luna": SimpleNamespace(available=True),
                "claude_sonnet_5": SimpleNamespace(available=True),
                "glm_5_2": SimpleNamespace(available=True),
            },
        )
        self.calls = 0
        self.bad_call = bad_call
        self.failure_kind = failure_kind

    async def hybrid_review(self, **_kwargs):
        self.calls += 1
        reviews = _valid_reviews()
        if self.failure_kind == "valid_research_veto":
            for key, updates in {
                "no_trade": {
                    "reason": "research model says stop",
                    "contributing_factors": ["research_only"],
                },
                "critique": {"verdict": "block", "reasoning": "research veto"},
                "risk": {"risk_level": "critical", "reasoning": "research risk"},
            }.items():
                payload = json.loads(reviews[key].content)
                payload.update(updates)
                reviews[key].content = json.dumps(payload)
        if self.calls != self.bad_call:
            return reviews
        if self.failure_kind == "missing_voice":
            reviews.pop("risk")
        elif self.failure_kind == "provider_error":
            reviews["risk"].raw_metadata["error_class"] = "HTTP_500"
        elif self.failure_kind == "wrong_model":
            reviews["risk"].raw_metadata["model"] = "openai/wrong-model"
        elif self.failure_kind == "mock_fallback":
            task = reviews["risk"].task
            reviews["risk"] = reviews["risk"].model_copy(
                update={
                    "decision": ModelRouteDecision(
                        task=task,
                        provider_name="mock",
                        model_name="mock",
                        reason="provider fallback",
                        fallback_reason="glm_5_2_request_failed",
                    ),
                    "raw_metadata": {
                        "provider": "mock",
                        "model": "mock",
                        "error_class": None,
                    },
                }
            )
        return reviews


def _loop(tmp_path, engine) -> RealMarketForecastLoopV2:
    return RealMarketForecastLoopV2(
        hybrid_engine=engine,
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
        model_authority_path=tmp_path / "missing_model_authority.json",
        model_authority_approved_roots=[tmp_path],
    )


def _earned_authority_bundle(tmp_path):
    now = datetime.now(timezone.utc)
    computed_at = now - timedelta(minutes=2)
    scope = model_probability_scope(
        ticker="KXMLBGAME-26JUL21NYYBOS-NYY-YES",
        title="Will the Yankees beat the Red Sox? Yes",
        category="Sports",
        decision_at=now,
        expiration=now + timedelta(days=1),
        live_phase=False,
    )
    evidence_root = tmp_path / "authority_artifacts"
    evidence_root.mkdir()
    row = {
        "evidence_mode": MODEL_EVIDENCE_MODE,
        "forward_calibrated": True,
        "receipt_bounded": True,
        "point_in_time": True,
        "retro_rows_included": 0,
        "independent_event_clusters": 300,
        "brier_edge_ci95": {"lower": 0.002, "upper": 0.01},
        "earned_weight": 0.12,
        "computed_at": computed_at.isoformat(),
        "received_through": (computed_at - timedelta(seconds=1)).isoformat(),
    }
    artifact_row = {
        **row,
        "independent_event_cluster_ids": [
            f"event-{index}" for index in range(300)
        ],
    }
    artifact = {
        "schema_version": MODEL_EVIDENCE_SCHEMA,
        "artifact_type": MODEL_EVIDENCE_SCHEMA,
        "generated_at": row["computed_at"],
        "evidence_mode": MODEL_EVIDENCE_MODE,
        "provider_models": sorted(EXPECTED_PROVIDER_MODELS),
        "promotion_authority": False,
        "scopes": {scope: artifact_row},
    }
    artifact_path = evidence_root / "evidence.json"
    artifact_bytes = json.dumps(artifact, sort_keys=True).encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    evidence = {
        **row,
        "evidence_ref": str(artifact_path),
        "evidence_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
    }
    registry_path = tmp_path / "model_authority.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": MODEL_AUTHORITY_SCHEMA,
                "promotions": [
                    {
                        "scope": scope,
                        "status": "PROMOTED",
                        "provider_models": list(
                            reversed(sorted(EXPECTED_PROVIDER_MODELS))
                        ),
                        "promoted_at": (
                            computed_at + timedelta(seconds=1)
                        ).isoformat(),
                        "evidence": evidence,
                    }
                ],
                "demotions": [],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, evidence_root


def test_openrouter_ready_requires_exact_config_and_valid_actual_envelopes(
    monkeypatch,
    no_project_env,
    tmp_path,
):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    router = ModelRouter(_write_config(tmp_path, _routing_config()))
    loop = _loop(tmp_path, HybridForecastEngine(router=router))

    assert loop._determine_model_mode() == MODEL_MODE_LIVE_HYBRID
    assert loop._review_contract_failures(_valid_reviews()) == []


def test_hybrid_provider_identity_is_order_insensitive_but_exact(tmp_path):
    engine = _FakeHybridEngine()
    engine.router.config.hybrid_providers = [
        "glm_5_2",
        "claude_sonnet_5",
        "gpt_5_6_luna",
        "gemini_3_6_flash",
    ]
    loop = _loop(tmp_path, engine)
    assert loop._determine_model_mode() == MODEL_MODE_LIVE_HYBRID

    engine.router.config.hybrid_providers = [
        "gemini_3_6_flash",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "claude_sonnet_5",
    ]
    assert loop._determine_model_mode() == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert "hybrid_provider_set_mismatch" in loop.model_degradation_reasons

    engine.router.config.hybrid_providers = [
        "gemini_3_6_flash",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
        "unexpected",
    ]
    assert loop._determine_model_mode() == MODEL_MODE_DEGRADED_QUANT_ONLY


@pytest.mark.parametrize(
    "legacy_panel",
    [
        ["gemini_3_5_flash", "gpt_5_6_terra"],
        ["deepseek_v4_flash", "minimax_m3"],
    ],
)
def test_legacy_two_model_panels_are_rejected(legacy_panel, tmp_path):
    engine = _FakeHybridEngine()
    engine.router.config.hybrid_providers = legacy_panel
    loop = _loop(tmp_path, engine)

    assert loop._determine_model_mode() == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert "hybrid_provider_set_mismatch" in loop.model_degradation_reasons


def test_seven_role_contract_uses_exact_four_model_panel():
    assert {
        key: (task.value, provider, model)
        for key, (task, provider, model) in REVIEW_ROUTE_CONTRACTS.items()
    } == {
        "primary_forecast": (
            "forecast_opinion",
            "gemini_3_6_flash",
            "google/gemini-3.6-flash",
        ),
        "rapid_forecast": (
            "rapid_forecast",
            "gpt_5_6_luna",
            "openai/gpt-5.6-luna",
        ),
        "no_trade": ("no_trade_reason", "glm_5_2", "z-ai/glm-5.2"),
        "critique": (
            "strategy_critique",
            "claude_sonnet_5",
            "anthropic/claude-sonnet-5",
        ),
        "risk": ("risk_critique", "glm_5_2", "z-ai/glm-5.2"),
        "thesis": (
            "market_thesis",
            "claude_sonnet_5",
            "anthropic/claude-sonnet-5",
        ),
        "calibration": ("calibration_note", "glm_5_2", "z-ai/glm-5.2"),
    }


@pytest.mark.parametrize(
    ("review_key", "updates", "expected"),
    [
        ("primary_forecast", {"dummy_probability": -0.01}, "response_probability_invalid:primary_forecast"),
        ("primary_forecast", {"dummy_probability": 1.01}, "response_probability_invalid:primary_forecast"),
        ("primary_forecast", {"dummy_probability": "NaN"}, "response_probability_invalid:primary_forecast"),
        ("primary_forecast", {"confidence_score": "Infinity"}, "response_confidence_invalid:primary_forecast"),
        (
            "primary_forecast",
            {"uncertainty_band": [0.95, 0.80]},
            "response_uncertainty_band_invalid:primary_forecast",
        ),
        (
            "primary_forecast",
            {"evidence_used": "supplied orderbook"},
            "response_evidence_used_invalid:primary_forecast",
        ),
        (
            "rapid_forecast",
            {"action": "submit_yes"},
            "response_action_invalid:rapid_forecast",
        ),
        (
            "rapid_forecast",
            {"entry_condition": ""},
            "response_entry_condition_invalid:rapid_forecast",
        ),
        ("critique", {"verdict": "YOLO"}, "response_verdict_invalid:critique"),
        ("risk", {"risk_level": "certain"}, "response_risk_level_invalid:risk"),
        ("thesis", {"confidence": 4}, "response_confidence_invalid:thesis"),
        ("no_trade", {"contributing_factors": "none"}, "response_factors_invalid:no_trade"),
        ("calibration", {"note": ""}, "response_note_invalid:calibration"),
    ],
)
def test_semantically_invalid_provider_payload_is_rejected(
    tmp_path,
    review_key,
    updates,
    expected,
):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    payload = json.loads(reviews[review_key].content)
    payload.update(updates)
    reviews[review_key].content = json.dumps(payload)

    assert expected in loop._review_contract_failures(reviews)
    assert loop._safe_probability("NaN", fallback=0) == 0


def test_legacy_keys_do_not_replace_missing_openrouter_key(
    monkeypatch,
    no_project_env,
    tmp_path,
):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-only")
    monkeypatch.setenv("MINIMAX_API_KEY", "legacy-only")
    router = ModelRouter(_write_config(tmp_path, _routing_config()))
    loop = _loop(tmp_path, HybridForecastEngine(router=router))

    assert loop._determine_model_mode() == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert "provider_unavailable:gemini_3_6_flash" in loop.model_degradation_reasons
    assert "provider_unavailable:gpt_5_6_luna" in loop.model_degradation_reasons
    assert "provider_unavailable:claude_sonnet_5" in loop.model_degradation_reasons
    assert "provider_unavailable:glm_5_2" in loop.model_degradation_reasons


def test_mock_fallback_envelope_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    task = reviews["risk"].task
    reviews["risk"] = reviews["risk"].model_copy(
        update={
            "decision": ModelRouteDecision(
                task=task,
                provider_name="mock",
                model_name="mock",
                reason="provider fallback",
                fallback_reason="glm_5_2_request_failed",
            ),
            "raw_metadata": {
                "provider": "mock",
                "model": "mock",
                "error_class": None,
            },
        }
    )

    failures = loop._review_contract_failures(reviews)
    assert "provider_mismatch:risk" in failures
    assert "provider_fallback:risk" in failures
    assert "metadata_provider_mismatch:risk" in failures


def test_wrong_or_duplicated_voice_identity_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    reviews["rapid_forecast"] = reviews["primary_forecast"].model_copy(deep=True)

    failures = loop._review_contract_failures(reviews)
    assert "envelope_task_mismatch:rapid_forecast" in failures
    assert "decision_task_mismatch:rapid_forecast" in failures
    assert "provider_mismatch:rapid_forecast" in failures
    assert "decision_model_mismatch:rapid_forecast" in failures


def test_unexpected_extra_voice_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    reviews["legacy_forecast"] = reviews["primary_forecast"]

    assert "unexpected_review:legacy_forecast" in loop._review_contract_failures(
        reviews
    )


def test_missing_required_schema_field_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    payload = json.loads(reviews["rapid_forecast"].content)
    payload.pop("entry_condition")
    reviews["rapid_forecast"].content = json.dumps(payload)

    assert "response_schema_invalid:rapid_forecast" in loop._review_contract_failures(
        reviews
    )


def test_wrong_model_envelope_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    reviews["risk"].raw_metadata["model"] = "openai/wrong-model"

    assert "metadata_model_mismatch:risk" in loop._review_contract_failures(reviews)


def test_one_missing_voice_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    reviews.pop("risk")

    assert "missing_review:risk" in loop._review_contract_failures(reviews)


def test_provider_error_envelope_is_rejected(tmp_path):
    loop = _loop(tmp_path, _FakeHybridEngine())
    reviews = _valid_reviews()
    reviews["risk"].raw_metadata["error_class"] = "HTTP_500"

    assert "provider_error:risk" in loop._review_contract_failures(reviews)


@pytest.mark.asyncio
async def test_one_bad_market_degrades_entire_run_to_no_trade_quant_only(
    monkeypatch,
    tmp_path,
):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    engine = _FakeHybridEngine(
        bad_call=2,
        failure_kind="missing_voice",
    )
    result = await _loop(tmp_path, engine).run(max_markets=3)

    assert engine.calls == 0
    assert result["model_mode"] == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert result["model_probability_authority"] == 0
    assert "non_live_market_data" in result["model_degradation_reasons"]
    assert all(opinion["model_summary"].startswith(MODEL_MODE_DEGRADED_QUANT_ONLY) for opinion in result["opinions"])
    assert all(
        opinion["no_trade_reason"]
        == "degraded quant-only - hybrid model validation failed; trading disabled"
        for opinion in result["opinions"]
    )
    assert all(
        "model_probability_authority=0" in opinion["calibration_notes"]
        for opinion in result["opinions"]
    )


@pytest.mark.asyncio
async def test_valid_live_hybrid_calls_are_research_only_without_earned_scope(
    monkeypatch,
    tmp_path,
):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    engine = _FakeHybridEngine(failure_kind="valid_research_veto")
    result = await _loop(tmp_path, engine).run(max_markets=1)

    assert engine.calls == 0
    assert result["model_mode"] == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert result["model_probability_authority"] == 0
    assert result["authorized_scope_count"] == 0
    assert len(result["model_probability_authority_by_scope"]) == 1
    decision = next(iter(result["model_probability_authority_by_scope"].values()))
    assert decision["authorized"] is False
    assert "model_mode_not_live_hybrid" in decision["blockers"]

    report = json.loads(
        (tmp_path / "artifacts" / "real_market_forecast_loop_report_v2.json").read_text()
    )
    opinion = result["opinions"][0]
    scores = report["markets"][0]
    assert opinion["dummy_probability"] == scores["dummy_statistical_probability"]
    expected_confidence = (
        float(scores["liquidity_score"])
        * float(scores["freshness_score"])
        * (1 - float(scores["settlement_risk_score"]))
    )
    assert float(opinion["confidence_score"]) == pytest.approx(expected_confidence, abs=0.0001)
    assert opinion["no_trade_reason"].startswith("degraded quant-only")
    assert opinion["model_summary"].startswith(MODEL_MODE_DEGRADED_QUANT_ONLY)
    assert any(
        note == "model_probability_authority=0"
        for note in opinion["calibration_notes"]
    )


@pytest.mark.asyncio
async def test_canonical_exact_scope_promotion_applies_only_earned_weight(
    monkeypatch,
    tmp_path,
):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    registry_path, evidence_root = _earned_authority_bundle(tmp_path)
    engine = _FakeHybridEngine()
    loop = RealMarketForecastLoopV2(
        hybrid_engine=engine,
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
        model_authority_path=registry_path,
        model_authority_approved_roots=[evidence_root],
    )

    result = await loop.run(max_markets=1)

    assert engine.calls == 0
    assert result["model_mode"] == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert result["model_probability_authority"] == 0
    assert result["authorized_scope_count"] == 0
    assert "non_live_market_data" in result["model_degradation_reasons"]


@pytest.mark.asyncio
async def test_single_contract_rehearsal_path_cannot_bypass_review_validation(
    monkeypatch,
    tmp_path,
):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    engine = _FakeHybridEngine(bad_call=1, failure_kind="missing_voice")
    loop = _RealMarketForecastLoopV2WithDetails(
        hybrid_engine=engine,
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
        model_authority_path=tmp_path / "missing_model_authority.json",
        model_authority_approved_roots=[tmp_path],
    )

    details = await loop.run_for_contract(
        "KXMLBGAME-26JUL21NYYBOS-NYY-YES",
        max_markets=1,
    )

    assert details is not None
    assert engine.calls == 0
    assert details["model_mode"] == MODEL_MODE_DEGRADED_QUANT_ONLY
    assert details["model_probability_authority"] == 0
    assert any(
        "non_live_market_data" in reason
        for reason in details["model_degradation_reasons"]
    )
    assert details["opinion"].model_summary.startswith(MODEL_MODE_DEGRADED_QUANT_ONLY)


@pytest.mark.asyncio
async def test_intentional_mock_mode_never_calls_model_and_never_trades(
    monkeypatch,
    tmp_path,
):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    engine = _FakeHybridEngine(live_enabled=False)
    result = await _loop(tmp_path, engine).run(max_markets=1)

    assert engine.calls == 0
    assert result["model_mode"] == MODEL_MODE_MOCK_ONLY
    assert result["model_probability_authority"] == 0
    assert result["opinions"][0]["model_summary"].startswith(MODEL_MODE_MOCK_ONLY)
    assert result["opinions"][0]["no_trade_reason"]
