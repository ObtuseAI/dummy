from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app


async def _mock_resolve(self, provider_name: str, *args, **kwargs):
    from model_router.resolver import ProviderResolutionResult

    if provider_name == "deepseek_v4_flash":
        return ProviderResolutionResult(
            provider_name="deepseek_v4_flash",
            status="LIVE_PROVEN",
            api_base="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            configured_model="deepseek-chat",
            resolved_model="deepseek-chat",
            resolved_by="model_list",
        )
    return ProviderResolutionResult(
        provider_name="minimax_m3",
        status="OPERATOR_MODEL_CONFIG_REQUIRED",
        api_base="https://api.minimax.chat",
        api_key_env="MINIMAX_API_KEY",
        configured_model="minimax-01",
        error_category="MODEL_NOT_FOUND",
        error_detail="all aliases unresolved",
    )


def test_v8_1_model_provider_resolution_endpoint_returns_200():
    client = TestClient(app)
    with patch("dashboard.backend.main.ModelProviderResolver.resolve", new=_mock_resolve):
        r = client.get("/api/v8/model-provider-resolution")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "deepseek_v4_flash" in data
    assert "minimax_m3" in data
    assert "repair_recommendation_path" in data


def test_v8_1_model_provider_resolution_redacts_keys():
    client = TestClient(app)
    with patch("dashboard.backend.main.ModelProviderResolver.resolve", new=_mock_resolve):
        r = client.get("/api/v8/model-provider-resolution")
    assert r.status_code == 200
    text = str(r.json())
    assert "sk-" not in text
    assert "BEGIN" not in text
    assert "DEEPSEEK_API_KEY" in text  # env name is fine
    assert "MINIMAX_API_KEY" in text


def test_v8_1_model_provider_resolution_status_values():
    client = TestClient(app)
    with patch("dashboard.backend.main.ModelProviderResolver.resolve", new=_mock_resolve):
        r = client.get("/api/v8/model-provider-resolution")
    data = r.json()
    assert data["deepseek_v4_flash"]["status"] == "LIVE_PROVEN"
    assert data["minimax_m3"]["status"] == "OPERATOR_MODEL_CONFIG_REQUIRED"
