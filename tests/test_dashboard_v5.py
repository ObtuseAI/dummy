from pathlib import Path
from fastapi.testclient import TestClient
from dashboard.backend.main import app

ROOT = Path(__file__).parent.parent


def test_v5_identity_endpoint():
    with TestClient(app) as client:
        r = client.get("/v5/identity")
        assert r.status_code == 200
        data = r.json()
        assert data["project"] == "Dummy"
        assert data["previous_name"] == "Dumby"


def test_v5_kalshi_status_endpoint():
    with TestClient(app) as client:
        r = client.get("/v5/kalshi/status")
        assert r.status_code == 200
        assert "credentials_present" in r.json()


def test_frontend_dist_built():
    dist = ROOT / "dashboard" / "frontend" / "dist"
    assert dist.exists()
    assert (dist / "index.html").exists()
