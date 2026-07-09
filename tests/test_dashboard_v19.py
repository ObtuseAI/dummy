from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v19_endpoints_return_activation_state_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v19/source-activation",
        "/api/v19/domain-watchlist",
        "/api/v19/domain-scan-cycle",
        "/api/v19/real-evidence-packets",
        "/api/v19/forecast-activation",
        "/api/v19/outcome-observer-v2",
        "/api/v19/calibration-bootstrap",
        "/api/v19/autonomous-compounding",
        "/api/v19/domain-scoreboard-v2",
        "/api/v19/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        assert response.json()["live_submit_disabled"] is True
