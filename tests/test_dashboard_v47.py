from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v47_routes import router
from tests.v47_test_helpers import assert_v47_report_named


def test_dashboard_v47_report() -> None:
    report = assert_v47_report_named("dashboard_v47_report_v1.json", "dashboard_status")
    assert "/api/v47/stable-sample-threshold-controller" in report["routes"]
    assert report["dashboard_can_trigger_probes"] is False
    assert report["dashboard_can_trigger_trading"] is False


def test_v47_api_routes_are_read_only() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v47/stable-sample-threshold-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["execution_bridge_present"] is False
    assert "v47_stable_sample_threshold_controller_report" in payload
