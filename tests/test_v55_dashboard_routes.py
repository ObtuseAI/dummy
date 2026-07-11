from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v55_routes import router
from predator_mesh.v55.reports import SAFETY_REPORT_NAMES, V55_ROUTES
from tests.v55_test_helpers import approval_input, assert_v55_report_named


def test_v55_dashboard_and_api_routes_are_read_only() -> None:
    dashboard = assert_v55_report_named("dashboard_v55_report_v1.json", "dashboard_status")
    assert dashboard["dashboard_status"] == "PASS"
    assert dashboard["routes"] == V55_ROUTES
    assert "/api/v55/dedicated-approval-input-resolver" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v55/dedicated-approval-input-resolver")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["api_can_create_quarantine_artifacts"] is False
    assert "v55_dedicated_approval_input_resolver_report" in payload


def test_v55_safety_reports_keep_all_execution_surfaces_locked() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v55_report_named(name, "safety_status", enabled=True, approval=approval_input())
        assert report["safety_status"] == "PASS"
        assert report["v55_execution_artifacts_created"] is False
        assert report["quarantine_release_path_present"] is False
        assert report["broker_payloads_created"] is False
        assert report["order_tickets_created"] is False
