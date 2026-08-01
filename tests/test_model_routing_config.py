from __future__ import annotations

import json
from pathlib import Path


from model_router.config import (
    CONFIG_PATH,
    ModelRoutingConfig,
    ProviderConfig,
    load_model_routing_config,
)


def test_default_config_file_exists():
    assert CONFIG_PATH.exists(), "configs/model_routing.json should exist"


def test_load_default_config():
    cfg = load_model_routing_config()
    assert cfg.mock_fallback_enabled is True
    assert cfg.live_model_calls_enabled is False
    assert cfg.max_prompt_length == 16000
    assert "glm_5_2" in cfg.provider_configs
    assert "minimax_m3" in cfg.provider_configs
    # DeepSeek was removed from the arsenal entirely on 2026-08-01, so the
    # provider must be absent rather than lingering as a fallback alias
    # target. Asserting the absence is what stops it drifting back in.
    assert "deepseek_v4_flash" not in cfg.provider_configs
    assert not any(
        "deepseek" in spec.model_name.lower()
        for spec in cfg.provider_configs.values()
    )
    # Retired from the roster in the same change.
    assert "gemini_3_6_flash" not in cfg.provider_configs
    assert not any(
        "gemini" in spec.model_name.lower()
        for spec in cfg.provider_configs.values()
    )
    assert cfg.hybrid_providers == [
        "gpt_5_6_terra",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
    ]


def test_provider_configs_are_parsed():
    cfg = load_model_routing_config()
    glm = cfg.provider_configs["glm_5_2"]
    assert isinstance(glm, ProviderConfig)
    assert glm.api_base == "https://openrouter.ai/api"
    assert glm.api_key_env == "OPENROUTER_API_KEY"
    assert glm.model_name == "z-ai/glm-5.2"
    assert glm.rpm == 60
    assert glm.timeout_seconds == 20.0
    assert glm.reasoning_effort == "high"
    assert glm.prompt_cost_per_million == 0.798
    assert glm.completion_cost_per_million == 2.508
    assert glm.max_retries == 0

    mx = cfg.provider_configs["minimax_m3"]
    assert mx.api_base == "https://openrouter.ai/api"
    assert mx.api_key_env == "OPENROUTER_API_KEY"
    assert mx.model_name == "minimax/minimax-m3"

    terra = cfg.provider_configs["gpt_5_6_terra"]
    assert terra.model_name == "openai/gpt-5.6-terra"
    assert terra.reasoning_effort == "low"
    # Terra's own prices. The seat previously held gemini-3.6-flash at
    # 1.5/7.5, which is why those literals were here -- they belong to the
    # retired model, not to this one.
    assert terra.prompt_cost_per_million == 1.0
    assert terra.completion_cost_per_million == 6.0
    assert terra.max_retries == 0

    luna = cfg.provider_configs["gpt_5_6_luna"]
    assert luna.model_name == "openai/gpt-5.6-luna"
    assert luna.reasoning_effort == "medium"
    # Luna was configured at 1.0/6.0 -- terra's prices, not its own, a 10x
    # overstatement that would push any cost-aware routing away from the
    # cheapest model in the arsenal. 0.10/0.60 is corroborated by the
    # OpenRouter models API, DumbMoney's model catalog, and DumbMoney's
    # roster test.
    assert luna.prompt_cost_per_million == 0.10
    assert luna.completion_cost_per_million == 0.60
    assert luna.max_retries == 0

    claude = cfg.provider_configs["claude_sonnet_5"]
    assert claude.model_name == "anthropic/claude-sonnet-5"
    assert claude.reasoning_effort == "high"
    assert claude.prompt_cost_per_million == 2.0
    assert claude.completion_cost_per_million == 10.0
    assert claude.max_retries == 0


def test_default_provider_mapping():
    cfg = load_model_routing_config()
    assert cfg.default_provider["forecast_opinion"] == "gpt_5_6_terra"
    assert cfg.default_provider["rapid_forecast"] == "gpt_5_6_luna"
    assert cfg.default_provider["trade_draft"] == "gpt_5_6_luna"
    assert cfg.default_provider["strategy_critique"] == "claude_sonnet_5"
    assert cfg.default_provider["market_thesis"] == "claude_sonnet_5"
    assert cfg.default_provider["risk_critique"] == "glm_5_2"
    assert cfg.default_provider["no_trade_reason"] == "glm_5_2"
    assert cfg.default_provider["calibration_note"] == "glm_5_2"
    assert cfg.default_provider["hybrid_review"] == "hybrid"


def test_blocked_prompt_categories():
    cfg = load_model_routing_config()
    assert "secret_leak" in cfg.blocked_prompt_categories
    assert "instruction_injection" in cfg.blocked_prompt_categories
    assert "order_endpoint" in cfg.blocked_prompt_categories
    assert "cap_modification" in cfg.blocked_prompt_categories


def test_secret_key_env_names():
    cfg = load_model_routing_config()
    assert "DEEPSEEK_API_KEY" in cfg.secret_key_env_names
    assert "MINIMAX_API_KEY" in cfg.secret_key_env_names
    assert "KALSHI_API_KEY_ID" in cfg.secret_key_env_names
    assert "KALSHI_API_PRIVATE_KEY_PEM" in cfg.secret_key_env_names


def test_fallback_when_file_missing(tmp_path: Path):
    missing = tmp_path / "nonexistent.json"
    cfg = load_model_routing_config(missing)
    assert isinstance(cfg, ModelRoutingConfig)
    assert cfg.provider_configs == {}
    assert cfg.mock_fallback_enabled is True


def test_load_from_custom_path(tmp_path: Path):
    path = tmp_path / "routing.json"
    data = {
        "default_provider": {"forecast_opinion": "mock"},
        "provider_configs": {
            "mock": {
                "api_base": "",
                "api_key_env": "",
                "model_name": "mock",
            }
        },
    }
    path.write_text(json.dumps(data))
    cfg = load_model_routing_config(path)
    assert cfg.default_provider["forecast_opinion"] == "mock"
