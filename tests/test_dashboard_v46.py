from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v46_routes import router
from tests.v46_test_helpers import assert_current_test_report


def test_dashboard_v46_report() -> None:
    assert_current_test_report(__file__)


def test_v46_api_routes_are_read_only() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v46/threshold-pursuit-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["execution_bridge_present"] is False
    assert "v46_readonly_observer_threshold_pursuit_controller_v1_report" in payload
