from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v26_test_helpers import assert_current_test_report


def test_dashboard_v26_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True


def test_dashboard_v26_endpoints_return_keyless_settlement_state_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v26/keyless-public-adapters",
        "/api/v26/keyless-probes",
        "/api/v26/weather-settlement",
        "/api/v26/crypto-settlement",
        "/api/v26/commodity-reference",
        "/api/v26/finance-macro-events",
        "/api/v26/sports-schedule-status",
        "/api/v26/public-events",
        "/api/v26/kalshi-readonly-join",
        "/api/v26/settlement-closure",
        "/api/v26/forecast-resolution",
        "/api/v26/forecast-cadence",
        "/api/v26/live-scoring-closure",
        "/api/v26/replay-to-live",
        "/api/v26/source-truth-v8",
        "/api/v26/adapter-sprint",
        "/api/v26/compounding-v10",
        "/api/v26/scoreboard-v11",
        "/api/v26/runtime-budget",
        "/api/v26/safety",
        "/api/v26/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
