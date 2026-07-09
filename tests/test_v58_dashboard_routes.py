from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v58_routes import router
from predator_mesh.v58.reports import SAFETY_REPORT_NAMES, V58_ROUTES
from tests.v58_test_helpers import assert_v58_report_named


def test_v58_dashboard_and_api_routes_are_read_only() -> None:
    dashboard = assert_v58_report_named("dashboard_v58_report_v1.json", "dashboard_status")
    assert dashboard["dashboard_status"] == "PASS"
    assert dashboard["routes"] == V58_ROUTES
    assert "/api/v58/quarantine-artifact-reviewer" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v58/quarantine-artifact-reviewer")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["api_can_create_approval_file"] is False
    assert payload["api_can_create_quarantine_artifacts"] is False
    assert payload["api_can_release_quarantine_artifacts"] is False
    assert "v58_quarantine_artifact_reviewer_report" in payload


def test_v58_safety_reports_keep_all_execution_surfaces_locked() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v58_report_named(name, "safety_status")
        assert report["safety_status"] == "PASS"
        assert report["approval_file_created"] is False
        assert report["default_quarantine_artifact_created"] is False
        assert report["quarantine_artifact_mutated"] is False
        assert report["v58_execution_artifacts_created"] is False
        assert report["quarantine_release_path_present"] is False
