from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v32_test_helpers import assert_current_test_report


def test_dashboard_v32_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True
    assert "/api/v32/source-recovery" in report["routes"]


def test_dashboard_v32_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v32/mission-state",
        "/api/v32/source-recovery",
        "/api/v32/gate",
        "/api/v32/minimal-probe-pass",
        "/api/v32/domain-recovery",
        "/api/v32/evidence",
        "/api/v32/closure",
        "/api/v32/scoring",
        "/api/v32/source-truth",
        "/api/v32/safety",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "github_pat_" not in response.text
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
