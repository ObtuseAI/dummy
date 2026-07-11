from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v54_routes import router
from predator_mesh.v54.reports import SAFETY_REPORT_NAMES, V54_ROUTES
from tests.v54_test_helpers import approval_input, assert_v54_report_named


def test_v54_dashboard_and_api_routes_are_read_only() -> None:
    dashboard = assert_v54_report_named("dashboard_v54_report_v1.json", "dashboard_status")
    assert dashboard["dashboard_status"] == "PASS"
    assert dashboard["routes"] == V54_ROUTES
    assert "/api/v54/exact-approval-controller" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v54/exact-approval-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["api_can_create_quarantine_artifacts"] is False
    assert "v54_exact_approval_controller_report" in payload


def test_v54_safety_reports_keep_all_execution_surfaces_locked() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v54_report_named(name, "safety_status", enabled=True, approval=approval_input())
        assert report["safety_status"] == "PASS"
        assert report["v54_execution_artifacts_created"] is False
        assert report["quarantine_release_path_present"] is False
        assert report["broker_payloads_created"] is False
        assert report["order_tickets_created"] is False
