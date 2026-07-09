from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v45_routes import router
from tests.v45_test_helpers import assert_current_test_report


def test_dashboard_v45_report() -> None:
    assert_current_test_report(__file__)


def test_v45_api_routes_are_read_only() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v45/observer-continuation-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["execution_bridge_present"] is False
    assert "v45_readonly_observer_continuation_controller_v1_report" in payload
