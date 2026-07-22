from fastapi.testclient import TestClient
from dashboard.backend.main import app

ENDPOINTS = [
    "/status", "/markets", "/forecasts", "/strategies", "/orders",
    "/positions", "/risk", "/proof", "/logs", "/repo-harvester/status",
    "/repo-harvester/repos", "/repo-harvester/reports",
]

# Mutating routes require a configured token even on localhost.
LOCALHOST = ("127.0.0.1", 50000)

def test_endpoints_exist():
    with TestClient(app) as client:
        for ep in ENDPOINTS:
            r = client.get(ep)
            assert r.status_code == 200, f"{ep} returned {r.status_code}"

def test_mode_set(monkeypatch):
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", "backend-test-token")
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post(
            "/mode/set",
            json={"mode": "READ_ONLY"},
            headers={"Authorization": "Bearer backend-test-token"},
        )
        assert r.status_code == 200
        assert r.json()["mode"] == "READ_ONLY"

def test_kill_switch(monkeypatch):
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", "backend-test-token")
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post(
            "/kill-switch/enable",
            json={"reason": "test"},
            headers={"Authorization": "Bearer backend-test-token"},
        )
        assert r.status_code == 200
        assert r.json()["active"] is True

def test_emergency_stop(monkeypatch):
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", "backend-test-token")
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post(
            "/emergency-stop",
            headers={"Authorization": "Bearer backend-test-token"},
        )
        assert r.status_code == 200
        assert r.json()["active"] is True

def test_websocket():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/status") as ws:
            data = ws.receive_json()
            assert "mode" in data
