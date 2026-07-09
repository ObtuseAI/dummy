from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert cfg.max_prompt_length == 16000
    assert "deepseek_v4_flash" in cfg.provider_configs
    assert "minimax_m3" in cfg.provider_configs


def test_provider_configs_are_parsed():
    cfg = load_model_routing_config()
    ds = cfg.provider_configs["deepseek_v4_flash"]
    assert isinstance(ds, ProviderConfig)
    assert ds.api_base == "https://openrouter.ai/api"
    assert ds.api_key_env == "OPENROUTER_API_KEY"
    assert ds.model_name == "deepseek/deepseek-chat"
    assert ds.rpm == 60
    assert ds.timeout_seconds == 20.0

    mx = cfg.provider_configs["minimax_m3"]
    assert mx.api_base == "https://openrouter.ai/api"
    assert mx.api_key_env == "OPENROUTER_API_KEY"
    assert mx.model_name == "minimax/minimax-01"


def test_default_provider_mapping():
    cfg = load_model_routing_config()
    assert cfg.default_provider["forecast_opinion"] == "deepseek_v4_flash"
    assert cfg.default_provider["strategy_critique"] == "minimax_m3"
    assert cfg.default_provider["risk_critique"] == "deepseek_v4_flash"
    assert cfg.default_provider["no_trade_reason"] == "minimax_m3"
    assert cfg.default_provider["trade_draft"] == "deepseek_v4_flash"
    assert cfg.default_provider["calibration_note"] == "minimax_m3"
    assert cfg.default_provider["market_thesis"] == "minimax_m3"
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
