from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v20_endpoints_return_cached_source_universe_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v20/source-universe",
        "/api/v20/source-candidates",
        "/api/v20/github-source-miner",
        "/api/v20/source-approval-gate",
        "/api/v20/official-public-adapters",
        "/api/v20/licensed-adapter-plans",
        "/api/v20/nasdaq-direction-terrain",
        "/api/v20/oil-direction-terrain",
        "/api/v20/crypto-direction-terrain",
        "/api/v20/weather-terrain",
        "/api/v20/sports-terrain",
        "/api/v20/evidence-router-v2",
        "/api/v20/research-swarm-v2",
        "/api/v20/forecast-pipeline-v2",
        "/api/v20/source-gap-recommendations",
        "/api/v20/compounding-control-plane-v3",
        "/api/v20/domain-scoreboard-v4",
        "/api/v20/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        assert response.json()["live_submit_disabled"] is True
