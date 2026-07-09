from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v30_test_helpers import assert_current_test_report


def test_dashboard_v30_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True


def test_dashboard_v30_endpoints_return_adapter_state_without_secrets() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v30/mission-state",
        "/api/v30/adapters",
        "/api/v30/fixtures",
        "/api/v30/normalization",
        "/api/v30/settlement",
        "/api/v30/closure-dry-run",
        "/api/v30/probe-readiness",
        "/api/v30/sports",
        "/api/v30/source-truth",
        "/api/v30/safety",
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
