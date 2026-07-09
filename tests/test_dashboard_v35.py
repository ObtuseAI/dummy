from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v35_test_helpers import assert_current_test_report

V35_ENDPOINTS = [
    "/api/v35/v34-qc",
    "/api/v35/frontend-build",
    "/api/v35/default-path",
    "/api/v35/enabled-path",
    "/api/v35/evidence-mode",
    "/api/v35/live-score-sample-readiness",
    "/api/v35/calibration-low-sample",
    "/api/v35/v34-route-smoke",
    "/api/v35/report-transform-consistency",
    "/api/v35/protected-hash",
    "/api/v35/no-execution-bridge-deep-recheck",
    "/api/v35/sports-fixture-only",
    "/api/v35/source-truth-v16",
    "/api/v35/partial-reduction",
    "/api/v35/sprint-v12",
    "/api/v35/compounding-v19",
    "/api/v35/market-class-scoreboard",
    "/api/v35/mission-state",
]


def test_dashboard_v35_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert report["read_only_only"] is True
    assert "/api/v35/v34-qc" in report["routes"]
    assert "/api/v35/mission-state" in report["routes"]
    assert len(report["routes"]) == 18


def test_dashboard_v35_endpoints_are_safe_and_artifact_backed() -> None:
    client = TestClient(app)
    for endpoint in V35_ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "github_pat_" not in response.text
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
