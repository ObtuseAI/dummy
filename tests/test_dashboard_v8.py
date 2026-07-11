from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app


async def _mock_forecast_opinions(*args, **kwargs):
    return {
        "source": "mock",
        "model_mode": "MOCK_ONLY",
        "kalshi_credentials_present": False,
        "opinions": [],
        "count": 0,
    }


async def _mock_live_smoke(*args, **kwargs):
    return {
        "live_model_status": "MOCK_ONLY",
        "model_mode": "MOCK_ONLY",
        "verdict": "PASS",
        "credential_status": {"all_ready": False},
        "call_results": [],
    }


def test_v8_routes_return_200():
    client = TestClient(app)
    endpoints = [
        "/v8/status",
        "/v8/model-providers",
        "/v8/live-smoke",
        "/v8/prompt-firewall",
        "/v8/output-firewall",
        "/v8/forecast-opinions",
        "/v8/calibration",
        "/v8/strategy-governor",
        "/v8/disagreement",
        "/v8/firewall-rehearsal",
        "/v8/proof-reports",
    ]
    with patch("archive.routes.v8_routes.RealMarketForecastLoopV2.run", new=_mock_forecast_opinions):
        with patch("archive.routes.v8_routes.LiveModelSmoke.run", new=_mock_live_smoke):
            for ep in endpoints:
                r = client.get(ep)
                assert r.status_code == 200, f"{ep} failed: {r.text}"


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


def test_v8_frontend_dist_exists():
    assert (Path("C:/src/engine/dummy/dashboard/frontend/dist/index.html")).exists()
