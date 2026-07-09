from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v23_test_helpers import assert_current_test_report


def test_dashboard_v23_endpoints_return_closure_state_without_secrets() -> None:
    assert_current_test_report(__file__)
    client = TestClient(app)
    endpoints = [
        "/api/v23/forecast-observer-closure",
        "/api/v23/crypto-outcome-observer",
        "/api/v23/weather-outcome-observer",
        "/api/v23/forecast-scoring",
        "/api/v23/calibration-update",
        "/api/v23/forecast-attribution",
        "/api/v23/source-truth-score",
        "/api/v23/tier0-adapter-closure",
        "/api/v23/cme-adapter-gate",
        "/api/v23/databento-adapter-gate",
        "/api/v23/eia-activation-closure",
        "/api/v23/rates-dxy-context",
        "/api/v23/nasdaq-oil-readiness",
        "/api/v23/forecast-lifecycle",
        "/api/v23/compounding-v6",
        "/api/v23/domain-scoreboard-v7",
        "/api/v23/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
