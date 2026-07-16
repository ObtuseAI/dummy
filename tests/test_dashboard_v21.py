from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v21_test_helpers import assert_current_test_report


def test_dashboard_v21_endpoints_return_activation_breakout_without_secrets() -> None:
    assert_current_test_report(__file__)
    client = TestClient(app)
    endpoints = [
        "/api/v21/source-activation-policy",
        "/api/v21/source-approval-cockpit",
        "/api/v21/official-public-activation",
        "/api/v21/eia-energy",
        "/api/v21/nws-weather",
        "/api/v21/crypto-public-exchange",
        "/api/v21/finance-macro-official",
        "/api/v21/nasdaq-bootstrap",
        "/api/v21/oil-bootstrap",
        "/api/v21/licensed-acquisition",
        "/api/v21/github-miner",
        "/api/v21/evidence-router-v3",
        "/api/v21/forecast-pipeline-v3",
        "/api/v21/compounding-v4",
        "/api/v21/domain-scoreboard-v5",
        "/api/v21/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
