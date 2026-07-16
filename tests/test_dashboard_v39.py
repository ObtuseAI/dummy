from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v39_test_helpers import assert_current_test_report


def test_dashboard_v39() -> None:
    report = assert_current_test_report(__file__)
    assert report["dashboard_status"] == "PASS"
    assert report["read_only_dashboard"] is True
    assert report["dashboard_can_trigger_probes"] is False
    assert report["dashboard_can_trigger_trading"] is False
    client = TestClient(app)
    for route in report["routes"]:
        response = client.get(route)
        assert response.status_code == 200, route
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
