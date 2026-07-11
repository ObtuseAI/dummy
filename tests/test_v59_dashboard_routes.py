from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v59_routes import router
from predator_mesh.v59.reports import SAFETY_REPORT_NAMES, V59_ROUTES
from tests.v59_test_helpers import approval_input, assert_v59_report_named


def test_v59_dashboard_and_api_routes_are_read_only() -> None:
    dashboard = assert_v59_report_named("dashboard_v59_report_v1.json", "dashboard_status")
    assert dashboard["dashboard_status"] == "PASS"
    assert dashboard["routes"] == V59_ROUTES
    assert "/api/v59/manual-approval-pipeline-controller" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v59/manual-approval-pipeline-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["api_can_create_approval_file"] is False
    assert payload["api_can_create_quarantine_artifacts"] is False
    assert payload["api_can_release_quarantine_artifacts"] is False
    assert "v59_manual_approval_pipeline_controller_report" in payload


def test_v59_safety_reports_keep_all_execution_surfaces_locked() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v59_report_named(name, "safety_status", approval=approval_input())
        assert report["safety_status"] == "PASS"
        assert report["approval_file_created"] is False
        assert report["unauthorized_artifact_mutation"] is False
        assert report["v59_execution_artifacts_created"] is False
        assert report["quarantine_release_path_present"] is False
