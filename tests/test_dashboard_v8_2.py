from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_v8_2_provider_credential_source_endpoint():
    client = TestClient(app)
    r = client.get("/api/v8/provider-credential-source")
    assert r.status_code == 200, r.text
    data = r.json()
    for provider in ("deepseek_v4_flash", "minimax_m3", "openrouter"):
        assert provider in data
        assert "api_key_env" in data[provider]
        assert "source" in data[provider]
        assert "route_mode" in data[provider]


def test_v8_2_provider_route_mode_endpoint():
    client = TestClient(app)
    r = client.get("/api/v8/provider-route-mode")
    assert r.status_code == 200, r.text
    data = r.json()
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        assert provider in data
        assert data[provider]["route_mode"]
        assert data[provider]["intended_key_env"]
        assert data[provider]["base_url_class"]


def test_v8_2_live_model_proof_endpoint():
    client = TestClient(app)
    r = client.get("/api/v8/live-model-proof")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "live_model_status" in data
    assert "model_mode" in data
    assert "verdict" in data


def test_v8_2_dashboard_redacts_provider_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-dashboard-secret")
    client = TestClient(app)
    r = client.get("/api/v8/provider-credential-source")
    assert r.status_code == 200
    text = str(r.json())
    assert "sk-dashboard-secret" not in text
