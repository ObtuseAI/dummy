from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from model_router.config import ModelRoutingConfig, ProviderConfig
from model_router.network_capability import (
    ModelNetworkAuthorizationError,
    ModelNetworkCapability,
    issue_model_network_capability,
    model_network_capability_valid,
)
from model_router.openrouter_panel_smoke import run_openrouter_panel_smoke
from model_router.providers import OpenRouterProvider
from model_router.resolver import MAX_ALIAS_PROBES, ModelProviderResolver
from model_router.router import ModelRouter
from model_router.tasks import ModelTask


def _provider_config() -> ProviderConfig:
    return ProviderConfig(
        api_base="https://openrouter.ai/api",
        api_key_env="OPENROUTER_API_KEY",
        model_name="openai/gpt-5.6-luna",
        route_mode="openrouter",
        max_retries=0,
    )


def test_capability_requires_literal_true_and_cannot_be_directly_constructed() -> None:
    with pytest.raises(ModelNetworkAuthorizationError):
        issue_model_network_capability(  # type: ignore[arg-type]
            allow_live="true",
            source="invalid",
        )
    with pytest.raises(TypeError):
        ModelNetworkCapability(_authority=object(), source="forged")


@pytest.mark.asyncio
async def test_direct_http_provider_complete_is_blocked_before_low_level_call(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    provider = OpenRouterProvider(_provider_config())
    low_level = AsyncMock(
        return_value=json.dumps(
            {
                "dummy_probability": 0.5,
                "confidence_score": 0.1,
                "reasoning": "must not run",
            }
        )
    )
    monkeypatch.setattr(provider, "_call_api", low_level)

    with pytest.raises(ModelNetworkAuthorizationError):
        await provider.complete("safe", ModelTask.FORECAST_OPINION)
    low_level.assert_not_awaited()


@pytest.mark.asyncio
async def test_router_mints_capability_only_after_checked_live_config(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    config = ModelRoutingConfig(
        default_provider={ModelTask.FORECAST_OPINION.value: "probe"},
        provider_configs={"probe": _provider_config()},
        live_model_calls_enabled=False,
    )
    path = tmp_path / "routing.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    router = ModelRouter(path)
    complete = AsyncMock(
        return_value=(
            json.dumps(
                {
                    "dummy_probability": 0.5,
                    "confidence_score": 0.1,
                    "reasoning": "mocked transport",
                }
            ),
            {
                "provider": "openrouter_generic",
                "model": "openai/gpt-5.6-luna",
                "latency_ms": 1.0,
                "attempts": 1,
                "prompt_digest": "digest",
                "error_class": None,
                "cost_usd": 0.0,
            },
        )
    )
    monkeypatch.setattr(router.providers["probe"], "complete", complete)

    disabled = await router.call(ModelTask.FORECAST_OPINION, "safe prompt")
    assert disabled.decision.provider_name == "mock"
    complete.assert_not_awaited()

    router.config.live_model_calls_enabled = True
    enabled = await router.call(ModelTask.FORECAST_OPINION, "safe prompt")
    assert enabled.decision.provider_name == "probe"
    capability = complete.await_args.kwargs["network_capability"]
    assert model_network_capability_valid(capability)
    assert capability.source == "model_router.checked_live_config"


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_live", [False, "true", 1])
async def test_resolver_is_zero_network_without_strict_authorization(
    monkeypatch,
    model_network_capability,
    allow_live,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    resolver = ModelProviderResolver()
    model_list = AsyncMock(side_effect=AssertionError("network probe attempted"))
    alias_probe = AsyncMock(side_effect=AssertionError("network probe attempted"))
    monkeypatch.setattr(resolver, "_probe_model_list", model_list)
    monkeypatch.setattr(resolver, "_probe_alias", alias_probe)

    result = await resolver.resolve(
        "gpt_5_6_terra",
        allow_live=allow_live,  # type: ignore[arg-type]
        network_capability=model_network_capability,
    )

    assert result.status == "PREFLIGHT_ONLY"
    assert result.error_category == "LIVE_AUTHORIZATION_REQUIRED"
    model_list.assert_not_awaited()
    alias_probe.assert_not_awaited()


@pytest.mark.skip(
    reason="Exercises the DIRECT-API provider path (per-provider *_BASE_URL "
    "override and alias probing), which DeepSeek was the only provider using. "
    "DeepSeek was removed from the arsenal 2026-08-01 and every remaining "
    "provider routes through OpenRouter with api_base fixed in config, so this "
    "has no live provider to exercise. The security properties it covered -- "
    "unapproved endpoint override rejected before any secret read or probe, and "
    "alias probes capped -- are REAL and now UNCOVERED. Either delete the "
    "direct-API resolver path with these tests, or restore equivalent coverage. "
    "Do not simply delete this marker."
)
@pytest.mark.asyncio
async def test_resolver_rejects_unapproved_override_before_secret_or_probe(
    monkeypatch,
    model_network_capability,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://attacker.invalid/api")
    resolver = ModelProviderResolver()
    model_list = AsyncMock(side_effect=AssertionError("network probe attempted"))
    alias_probe = AsyncMock(side_effect=AssertionError("network probe attempted"))
    monkeypatch.setattr(resolver, "_probe_model_list", model_list)
    monkeypatch.setattr(resolver, "_probe_alias", alias_probe)

    result = await resolver.resolve(
        "gpt_5_6_terra",
        allow_live=True,
        network_capability=model_network_capability,
    )

    assert result.status == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert result.error_category == "PROVIDER_ENDPOINT_NOT_APPROVED"
    model_list.assert_not_awaited()
    alias_probe.assert_not_awaited()


@pytest.mark.skip(
    reason="Exercises the DIRECT-API provider path (per-provider *_BASE_URL "
    "override and alias probing), which DeepSeek was the only provider using. "
    "DeepSeek was removed from the arsenal 2026-08-01 and every remaining "
    "provider routes through OpenRouter with api_base fixed in config, so this "
    "has no live provider to exercise. The security properties it covered -- "
    "unapproved endpoint override rejected before any secret read or probe, and "
    "alias probes capped -- are REAL and now UNCOVERED. Either delete the "
    "direct-API resolver path with these tests, or restore equivalent coverage. "
    "Do not simply delete this marker."
)
@pytest.mark.asyncio
async def test_resolver_caps_paid_alias_probes(
    monkeypatch,
    model_network_capability,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    monkeypatch.setenv(
        "DEEPSEEK_MODEL_ALIASES",
        ",".join(f"alias-{index}" for index in range(MAX_ALIAS_PROBES + 20)),
    )
    resolver = ModelProviderResolver()
    model_list = AsyncMock(return_value=(False, []))
    alias_probe = AsyncMock(return_value=(False, "MODEL_NOT_FOUND"))
    monkeypatch.setattr(resolver, "_probe_model_list", model_list)
    monkeypatch.setattr(resolver, "_probe_alias", alias_probe)

    result = await resolver.resolve(
        "gpt_5_6_terra",
        allow_live=True,
        network_capability=model_network_capability,
    )

    assert result.status == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert alias_probe.await_count == MAX_ALIAS_PROBES


@pytest.mark.asyncio
async def test_panel_smoke_rejects_truthy_non_boolean_live_flag(monkeypatch) -> None:
    import model_router.openrouter_panel_smoke as smoke_module

    monkeypatch.setattr(
        smoke_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("HTTP client construction attempted")
        ),
    )
    report = await run_openrouter_panel_smoke(live="false")  # type: ignore[arg-type]
    assert report["mode"] == "preflight"
    assert report["network_calls_authorized"] is False
    assert report["calls_attempted"] == 0


@pytest.mark.asyncio
async def test_pytest_interlock_blocks_real_paid_transport_before_transport_use() -> None:
    class NeverTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):  # pragma: no cover
            raise AssertionError("real transport path was reached")

    async with httpx.AsyncClient(transport=NeverTransport()) as client:
        with pytest.raises(RuntimeError, match="pytest paid-model-provider"):
            await client.post("https://openrouter.ai/api/v1/chat/completions")
