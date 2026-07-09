from pathlib import Path
from fastapi.testclient import TestClient
from dashboard.backend.main import app


def test_v7_routes_return_200():
    client = TestClient(app)
    endpoints = [
        "/v7/identity",
        "/v7/model-router/status",
        "/v7/forecast/opinion",
        "/v7/strategies/intelligence",
        "/v7/reports/status",
    ]
    for ep in endpoints:
        r = client.get(ep)
        assert r.status_code == 200, f"{ep} failed: {r.text}"


def test_v7_frontend_dist_exists():
    assert (Path("C:/src/engine/dummy/dashboard/frontend/dist/index.html")).exists()
