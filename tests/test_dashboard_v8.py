from fastapi.testclient import TestClient

from dashboard.backend.main import app

def test_v8_routes_return_200():
    client = TestClient(app)
    expected_statuses = {
        "/v8/status": 200,
        "/v8/model-providers": 200,
        "/v8/live-smoke": 200,
        "/v8/prompt-firewall": 200,
        "/v8/output-firewall": 200,
        "/v8/forecast-opinions": 200,
        "/v8/calibration": 200,
        "/v8/strategy-governor": 200,
        "/v8/disagreement": 200,
        # Rehearsal executes a firewall path and stays operator-authenticated,
        # including on the explicit test-only archive surface.
        "/v8/firewall-rehearsal": 503,
        "/v8/proof-reports": 200,
    }
    for ep, expected in expected_statuses.items():
        r = client.get(ep)
        assert r.status_code == expected, f"{ep} failed: {r.text}"


def test_v8_status_has_no_secrets():
    client = TestClient(app)
    r = client.get("/v8/status")
    assert r.status_code == 200
    payload = r.json()
    text = str(payload)
    assert "sk-" not in text
    assert "BEGIN" not in text
    assert "api_key" not in text.lower()


def test_v8_model_providers_redacted():
    client = TestClient(app)
    r = client.get("/v8/model-providers")
    assert r.status_code == 200
    data = r.json()
    for name, status in data["providers"].items():
        assert status.get("redacted") is True, f"{name} not redacted"
        assert "api_key" not in str(status).lower()
        assert "private_key" not in str(status).lower()

