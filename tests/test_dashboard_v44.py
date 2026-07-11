from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v44_routes import router
from tests.v44_test_helpers import assert_current_test_report


def test_dashboard_v44_report() -> None:
    assert_current_test_report(__file__)


def test_v44_api_routes_are_read_only() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v44/observer-scaleout-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert payload["execution_bridge_present"] is False
    assert "v44_readonly_observer_scaleout_controller_v1_report" in payload
