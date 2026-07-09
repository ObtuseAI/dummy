from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v22_test_helpers import assert_current_test_report


def test_dashboard_v22_endpoints_return_breakthrough_state_without_secrets() -> None:
    assert_current_test_report(__file__)
    client = TestClient(app)
    endpoints = [
        "/api/v22/edge-role-classifier",
        "/api/v22/evidence-normalizer",
        "/api/v22/crypto-spot-edge",
        "/api/v22/weather-edge",
        "/api/v22/commodity-context-guard",
        "/api/v22/finance-context-guard",
        "/api/v22/market-event-mapper",
        "/api/v22/kalshi-market-mapping",
        "/api/v22/forecast-write-breakthrough",
        "/api/v22/outcome-observer-queue",
        "/api/v22/ledger-writes",
        "/api/v22/edge-source-acquisition",
        "/api/v22/github-adapter-queue",
        "/api/v22/compounding-v5",
        "/api/v22/domain-scoreboard-v6",
        "/api/v22/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
