from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v56_routes import router
from predator_mesh.v56.reports import SAFETY_REPORT_NAMES, V56_ROUTES
from tests.v56_test_helpers import assert_v56_report_named


def test_v56_dashboard_and_api_routes_are_read_only() -> None:
    dashboard = assert_v56_report_named("dashboard_v56_report_v1.json", "dashboard_status")
    assert dashboard["dashboard_status"] == "PASS"
    assert dashboard["routes"] == V56_ROUTES
    assert "/api/v56/operator-handoff-controller" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v56/operator-handoff-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["api_can_create_approval_file"] is False
    assert payload["api_can_create_quarantine_artifacts"] is False
    assert "v56_operator_handoff_controller_report" in payload


def test_v56_safety_reports_keep_all_execution_surfaces_locked() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v56_report_named(name, "safety_status")
        assert report["safety_status"] == "PASS"
        assert report["approval_file_created"] is False
        assert report["quarantine_artifact_instance_created"] is False
        assert report["v56_execution_artifacts_created"] is False
        assert report["quarantine_release_path_present"] is False
