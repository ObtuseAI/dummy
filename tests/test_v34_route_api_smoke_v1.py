from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from predator_mesh.v35.run import V34_SMOKE_ENDPOINTS
from tests.v35_test_helpers import assert_current_test_report


def test_v34_route_api_smoke_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v34_route_api_smoke_v1_status"] == "PASS"
    assert report["endpoints_smoked"] == len(V34_SMOKE_ENDPOINTS)
    assert report["all_http_200"] is True


def test_v34_smoke_endpoints_return_200() -> None:
    client = TestClient(app)
    for endpoint in V34_SMOKE_ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.status_code}"
        assert "BEGIN PRIVATE KEY" not in response.text
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
        assert payload["execution_bridge_present"] is False
