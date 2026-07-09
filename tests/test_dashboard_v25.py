from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v25_test_helpers import assert_current_test_report


def test_dashboard_v25_endpoints_return_market_class_state_without_secrets() -> None:
    assert_current_test_report(__file__)
    client = TestClient(app)
    endpoints = [
        "/api/v25/market-class-ontology",
        "/api/v25/market-class-registry",
        "/api/v25/evidence-to-market-mapper",
        "/api/v25/settlement-mapping",
        "/api/v25/forecast-cadence",
        "/api/v25/no-trade-quality",
        "/api/v25/live-observer-loop",
        "/api/v25/market-class-scoring",
        "/api/v25/replay-factory",
        "/api/v25/calibration-v5",
        "/api/v25/source-truth-v7",
        "/api/v25/approved-market-class-discovery",
        "/api/v25/source-stack-builder",
        "/api/v25/forecast-ledger",
        "/api/v25/adapter-acceleration",
        "/api/v25/compounding-v9",
        "/api/v25/scoreboard-v10",
        "/api/v25/runtime-budget",
        "/api/v25/safety",
        "/api/v25/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
