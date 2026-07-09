from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v33_test_helpers import assert_current_test_report


def test_dashboard_v33_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True
    assert "/api/v33/operator-enabled-probe-run" in report["routes"]


def test_dashboard_v33_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v33/operator-enabled-probe-run",
        "/api/v33/exact-gate-ack",
        "/api/v33/minimal-live-public-probe",
        "/api/v33/weather-enabled-probe",
        "/api/v33/crypto-enabled-probe",
        "/api/v33/public-event-enabled-probe",
        "/api/v33/kalshi-readonly-enabled-probe",
        "/api/v33/live-public-evidence",
        "/api/v33/settlement-evidence-join",
        "/api/v33/due-forecast-observation",
        "/api/v33/live-score-observation",
        "/api/v33/live-calibration-observation",
        "/api/v33/public-probe-cache",
        "/api/v33/enabled-probe-audit",
        "/api/v33/sports-probe-exclusion",
        "/api/v33/source-truth-v14",
        "/api/v33/partial-reduction",
        "/api/v33/probe-sprint-v10",
        "/api/v33/compounding-v17",
        "/api/v33/market-class-scoreboard",
        "/api/v33/mission-state",
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
