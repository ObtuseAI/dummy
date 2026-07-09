from __future__ import annotations

from model_router.route_mode import ProviderRouteMode, ProviderRouteModeResolver


def test_deepseek_native_route():
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://api.deepseek.com", "deepseek-chat"
    )
    assert result.route_mode == ProviderRouteMode.PROVIDER_NATIVE_DEEPSEEK
    assert result.intended_key_env == "DEEPSEEK_API_KEY"
    assert result.base_url_class == "deepseek_native"


def test_minimax_native_route():
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "minimax_m3", "https://api.minimax.chat", "minimax-01"
    )
    assert result.route_mode == ProviderRouteMode.PROVIDER_NATIVE_MINIMAX
    assert result.intended_key_env == "MINIMAX_API_KEY"
    assert result.base_url_class == "minimax_native"


def test_openrouter_route_by_url():
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://openrouter.ai/api", "deepseek/deepseek-v3"
    )
    assert result.route_mode == ProviderRouteMode.OPENROUTER
    assert result.intended_key_env == "OPENROUTER_API_KEY"
    assert result.base_url_class == "openrouter"


def test_openrouter_route_by_model_format():
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://api.example.com", "deepseek/deepseek-v3"
    )
    assert result.route_mode == ProviderRouteMode.OPENROUTER


def test_operator_config_required_for_unknown_provider():
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "unknown_provider", "https://unknown.example.com", "unknown-model"
    )
    assert result.route_mode == ProviderRouteMode.OPERATOR_CONFIG_REQUIRED
