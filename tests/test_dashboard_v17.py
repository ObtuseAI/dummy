from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v17_endpoints_return_truth_loop_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v17/outcome-ledger",
        "/api/v17/forecast-snapshots",
        "/api/v17/calibration",
        "/api/v17/outcome-attribution",
        "/api/v17/bloodline-truth",
        "/api/v17/improvement-proposals",
        "/api/v17/domain-baselines",
        "/api/v17/outcome-observer",
        "/api/v17/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
