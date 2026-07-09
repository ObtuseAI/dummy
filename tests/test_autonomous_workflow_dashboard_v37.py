from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v37_test_helpers import assert_current_test_report


def test_autonomous_workflow_dashboard_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert "/api/v37/mission-state" in report["routes"]
    assert report["read_only_dashboard"] is True
    client = TestClient(app)
    for route in report["routes"]:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.json()["live_submit_disabled"] is True
