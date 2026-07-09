from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v27_test_helpers import assert_current_test_report


def test_dashboard_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True


def test_dashboard_v27_endpoints_return_resolution_state_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v27/integration-mode-probes",
        "/api/v27/public-probe-matrix",
        "/api/v27/settlement-rule-library",
        "/api/v27/kalshi-settlement-rules",
        "/api/v27/due-forecast-resolution",
        "/api/v27/weather-live-settlement",
        "/api/v27/crypto-live-settlement",
        "/api/v27/commodity-macro-settlement",
        "/api/v27/sports-terms",
        "/api/v27/sports-adapter-stub",
        "/api/v27/live-scoring-closure",
        "/api/v27/live-calibration",
        "/api/v27/forecast-cadence",
        "/api/v27/observer-queue",
        "/api/v27/source-truth-v9",
        "/api/v27/partial-reduction",
        "/api/v27/adapter-sprint",
        "/api/v27/compounding-v11",
        "/api/v27/scoreboard-v12",
        "/api/v27/runtime-budget",
        "/api/v27/safety",
        "/api/v27/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
