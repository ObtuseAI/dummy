from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v18_endpoints_return_domain_intelligence_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v18/domain-intelligence",
        "/api/v18/research-packets",
        "/api/v18/evidence-stacks",
        "/api/v18/source-truth",
        "/api/v18/domain-baselines",
        "/api/v18/settlement-mapper",
        "/api/v18/domain-scoreboard",
        "/api/v18/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        assert response.json()["live_submit_disabled"] is True
