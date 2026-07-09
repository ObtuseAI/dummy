from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v34_test_helpers import assert_current_test_report


def test_dashboard_v34_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True
    assert "/api/v34/operator-enabled-probe-run-reconciliation" in report["routes"]
    assert "/api/v34/transport-guard" in report["routes"]


def test_dashboard_v34_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    endpoints = [
        "/api/v34/operator-enabled-probe-run-reconciliation",
        "/api/v34/exact-gate-ack",
        "/api/v34/bounded-readonly-public-probe",
        "/api/v34/weather-observation-reconciliation",
        "/api/v34/crypto-price-reconciliation",
        "/api/v34/public-event-reference-reconciliation",
        "/api/v34/kalshi-readonly-rule-reconciliation",
        "/api/v34/live-evidence-reconciliation",
        "/api/v34/settlement-join-reconciliation",
        "/api/v34/due-forecast-closure-reconciliation",
        "/api/v34/live-score-closure-reconciliation",
        "/api/v34/live-calibration-reconciliation",
        "/api/v34/probe-run-artifact-cache",
        "/api/v34/reconciled-probe-audit",
        "/api/v34/sports-probe-exclusion",
        "/api/v34/source-truth-v15",
        "/api/v34/partial-reduction",
        "/api/v34/probe-reconciliation-sprint-v11",
        "/api/v34/compounding-v18",
        "/api/v34/market-class-scoreboard",
        "/api/v34/transport-guard",
        "/api/v34/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "github_pat_" not in response.text
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
