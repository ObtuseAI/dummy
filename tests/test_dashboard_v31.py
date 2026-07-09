from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v31_test_helpers import assert_current_test_report


def test_dashboard_v31_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True
    assert "/api/v31/gate" in report["routes"]


def test_dashboard_v31_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v31/mission-state",
        "/api/v31/gate",
        "/api/v31/probe-runner",
        "/api/v31/evidence",
        "/api/v31/probes",
        "/api/v31/closure",
        "/api/v31/scoring",
        "/api/v31/cache-audit",
        "/api/v31/source-truth",
        "/api/v31/safety",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "github_pat_" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
