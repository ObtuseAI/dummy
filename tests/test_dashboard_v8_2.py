from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from dashboard.backend import main as backend
from dashboard.backend.main import app


def test_v8_2_provider_credential_source_endpoint():
    response = TestClient(app).get("/api/v8/provider-credential-source")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["provider_contacted"] is False
    assert data["data_status"] == "credential_presence_only"
    for provider in ("claude_sonnet_5", "gpt_5_6_luna", "glm_5_2", "gemini_3_6_flash"):
        row = data["providers"][provider]
        assert row["required_env_name"] == "OPENROUTER_API_KEY"
        assert row["route_mode"] == "openrouter"
        assert isinstance(row["present"], bool)


def test_v8_2_provider_route_mode_endpoint():
    response = TestClient(app).get("/api/v8/provider-route-mode")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["provider_contacted"] is False
    for provider in ("claude_sonnet_5", "gpt_5_6_luna", "glm_5_2", "gemini_3_6_flash"):
        row = data["providers"][provider]
        assert row["route_mode"] == "openrouter"
        assert row["required_env_name"] == "OPENROUTER_API_KEY"
        assert row["model_name"]


def test_v8_2_live_model_proof_endpoint_is_fail_closed():
    response = TestClient(app).get("/api/v8/live-model-proof")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "verdict" in data
    assert data["evidence_authority"] is False
    assert data["order_authority"] is False
    assert data["provider_contacted_by_dashboard"] is False
    assert data["source"]["smoke"] == "artifacts/dummy/openrouter_four_model_smoke_v1.json"
    assert "live_model_smoke_report_v3" not in response.text


def test_v8_2_dashboard_redacts_provider_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-dashboard-secret")
    response = TestClient(app).get("/api/v8/provider-credential-source")
    assert response.status_code == 200
    assert "sk-dashboard-secret" not in response.text


def test_v8_2_live_model_proof_requires_exact_unique_four_model_panel(tmp_path, monkeypatch):
    models = {
        "gemini_3_6_flash": "google/gemini-3.6-flash",
        "gpt_5_6_luna": "openai/gpt-5.6-luna",
        "claude_sonnet_5": "anthropic/claude-sonnet-5",
        "glm_5_2": "z-ai/glm-5.2",
    }
    config_path = tmp_path / "configs" / "model_routing.json"
    smoke_path = tmp_path / "artifacts" / "dummy" / "openrouter_four_model_smoke_v1.json"
    config_path.parent.mkdir(parents=True)
    smoke_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({
            "live_model_calls_enabled": True,
            "hybrid_providers": list(models),
            "provider_configs": {
                provider: {
                    "model_name": model,
                    "route_mode": "openrouter",
                    "api_key_env": "OPENROUTER_API_KEY",
                }
                for provider, model in models.items()
            },
        }),
        encoding="utf-8",
    )

    tasks = {
        "gemini_3_6_flash": "forecast_opinion",
        "gpt_5_6_luna": "rapid_forecast",
        "claude_sonnet_5": "strategy_critique",
        "glm_5_2": "risk_critique",
    }

    def call(provider, model):
        return {
            "attempts": 1,
            "http_status": 200,
            "provider_alias": provider,
            "requested_model": model,
            "response_model": model,
            "task": tasks[provider],
            "status": "LIVE_PROVEN",
            "response_schema_ok": True,
            "model_identity_ok": True,
            "response_content_stored": False,
        }

    smoke = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live",
        "status": "LIVE_PROVEN",
        "all_models_live_proven": True,
        "secret_free": True,
        "response_content_stored": False,
        "calls_attempted": 4,
        "call_cap": 4,
        "expected_panel": [
            {"provider_alias": provider, "model": model}
            for provider, model in models.items()
        ],
        "call_results": [call(provider, model) for provider, model in models.items()],
    }
    smoke_path.write_text(json.dumps(smoke), encoding="utf-8")
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    exact = TestClient(app).get("/api/v8/live-model-proof").json()
    assert exact["proof_current_for_active_hybrid"] is True
    assert exact["evidence_authority"] is False
    assert exact["authorities"] == {
        "evidence": False,
        "probability": False,
        "order": False,
    }

    smoke["call_results"].append(call("glm_5_2", "z-ai/glm-5.2"))
    smoke_path.write_text(json.dumps(smoke), encoding="utf-8")
    extra = TestClient(app).get("/api/v8/live-model-proof").json()
    assert extra["proof_current_for_active_hybrid"] is False
