from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_v8_1_model_provider_resolution_is_configuration_only():
    client = TestClient(app)
    # A dashboard GET must not instantiate or invoke the network resolver.
    with patch("model_router.resolver.ModelProviderResolver.resolve") as resolve:
        response = client.get("/api/v8/model-provider-resolution")
    assert response.status_code == 200, response.text
    resolve.assert_not_called()
    data = response.json()
    assert data["hybrid_providers"] == [
        "gemini_3_6_flash",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
    ]
    assert data["data_status"] == "configuration_only_no_provider_contact"
    assert data["provider_contacted"] is False
    assert data["live_model_calls_enabled"] is False


def test_v8_1_model_provider_resolution_reports_exact_active_models():
    data = TestClient(app).get("/api/v8/model-provider-resolution").json()
    providers = data["providers"]
    assert providers["claude_sonnet_5"]["model_name"] == "anthropic/claude-sonnet-5"
    assert providers["gpt_5_6_luna"]["model_name"] == "openai/gpt-5.6-luna"
    assert providers["glm_5_2"]["model_name"] == "z-ai/glm-5.2"
    assert providers["gemini_3_6_flash"]["model_name"] == "google/gemini-3.6-flash"
    assert all(
        provider["status"] == "CONFIGURED_NOT_PROBED_BY_DASHBOARD"
        for provider in providers.values()
    )


def test_v8_1_model_provider_resolution_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-dashboard-secret-value")
    response = TestClient(app).get("/api/v8/model-provider-resolution")
    text = response.text
    assert "sk-dashboard-secret-value" not in text
    assert "OPENROUTER_API_KEY" in text
