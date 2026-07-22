"""Security lockdown tests for the dashboard backend (audit Task 1).

Covers:
  * CORS is no longer wildcard — only the Vite dev origins are allowed.
  * Privileged routes reject every caller when DUMMY_OPERATOR_TOKEN is unset;
    loopback is not treated as an authentication boundary.
  * With DUMMY_OPERATOR_TOKEN set, a valid bearer / X-Operator-Token header
    is required from any caller; wrong or missing tokens are rejected.
"""
import pytest
import json
import os
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient

from dashboard.backend.main import app
from dashboard.backend.operator_auth import ENV_VAR

LOCALHOST = ("127.0.0.1", 50000)
REMOTE = ("203.0.113.10", 50000)  # TestClient default ("testclient") is also non-localhost

MUTATING_ROUTES = [
    ("/mode/set", {"mode": "READ_ONLY"}, 200),
    ("/kill-switch/enable", {"reason": "test"}, 200),
    ("/kill-switch/disable", None, 200),
    ("/emergency-stop", None, 200),
    # Authentication succeeds locally, then these honest unwired routes fail
    # closed instead of returning fabricated cancellation success.
    ("/orders/cancel", {"order_id": "t1"}, 501),
    ("/orders/cancel-all", None, 501),
]


@pytest.fixture(autouse=True)
def _no_operator_token(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)


# --- CORS -------------------------------------------------------------------

def test_cors_no_longer_wildcard():
    with TestClient(app) as client:
        r = client.get("/status", headers={"Origin": "http://evil.example"})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") != "*"
        assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # `npm run preview` origins (launch_dummy_dashboard.bat serves the built UI on 4173)
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)
def test_cors_allows_vite_dev_origins(origin):
    with TestClient(app) as client:
        r = client.options(
            "/status",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_rejects_other_origins():
    with TestClient(app) as client:
        r = client.options(
            "/status",
            headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert r.status_code == 400


def test_operator_auth_status_is_usable_and_never_returns_secret(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "status-probe-secret")
    with TestClient(app, client=LOCALHOST) as client:
        locked = client.get("/operator-auth/status")
        unlocked = client.get(
            "/operator-auth/status",
            headers={"Authorization": "Bearer status-probe-secret"},
        )
    assert locked.json()["configured"] is True
    assert locked.json()["authenticated"] is False
    assert unlocked.json()["authenticated"] is True
    assert unlocked.json()["secret_returned"] is False
    assert "status-probe-secret" not in unlocked.text


def test_production_import_does_not_import_or_mount_archive_routers():
    env = dict(os.environ)
    env.pop("DUMMY_DASHBOARD_ARCHIVE_SURFACE", None)
    code = (
        "import json,sys; "
        "from fastapi.testclient import TestClient; "
        "from dashboard.backend.main import app; "
        "paths={getattr(r,'path','') for r in app.routes}; "
        "response=TestClient(app).get('/v3/kalshi/status'); "
        "print(json.dumps({'surface':app.state.dashboard_surface,"
        "'count':app.state.archive_router_count,'v3_status':response.status_code,"
        "'archive_modules':[n for n in sys.modules if n.startswith('archive.routes.v')],"
        "'has_v304':any(p.startswith('/api/v304') for p in paths)}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.fspath(os.path.dirname(os.path.dirname(__file__))),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data == {
        "surface": "production",
        "count": 0,
        "v3_status": 404,
        "archive_modules": [],
        "has_v304": False,
    }


def test_production_frontend_hides_archive_and_synthetic_primary_screens():
    source = (Path(__file__).parents[1] / "dashboard" / "frontend" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    assert "VITE_DUMMY_ARCHIVE_SURFACE === 'offline-dev'" in source
    assert "ARCHIVE_SURFACE_ENABLED && <details" in source
    assert "const ARCHIVE_ONLY_LABELS = new Set(['Adapters', 'Strategy Scan', 'Proposed Trades'])" in source
    assert "return ARCHIVE_SURFACE_ENABLED ? <ArchivedStageView" in source


# --- Token unset: every caller fails closed, including localhost ------------

@pytest.mark.parametrize("path,body,expected_local_status", MUTATING_ROUTES)
def test_mutating_route_rejects_non_localhost_when_token_unset(path, body, expected_local_status):
    with TestClient(app, client=REMOTE) as client:
        r = client.post(path, json=body)
        assert r.status_code == 503, f"{path} returned {r.status_code}"


@pytest.mark.parametrize("path,body,expected_local_status", MUTATING_ROUTES)
def test_mutating_route_rejects_localhost_when_token_unset(path, body, expected_local_status):
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post(path, json=body)
        assert r.status_code == 503, f"{path} returned {r.status_code}"


@pytest.mark.parametrize("path", ["/api/operator/prepare", "/api/operator/install"])
def test_operator_authority_writes_reject_non_localhost_when_token_unset(path):
    with TestClient(app, client=REMOTE) as client:
        r = client.post(path)
        assert r.status_code == 503


def test_operator_control_one_shot_live_rejects_non_localhost_when_token_unset():
    with TestClient(app, client=REMOTE) as client:
        r = client.post("/api/operator-control/one-shot-live", json={})
        assert r.status_code == 503


def test_operator_control_live_submit_write_rejects_non_localhost_when_token_unset():
    with TestClient(app, client=REMOTE) as client:
        r = client.post("/api/operator-control/external-prereqs/live-submit/write", json={})
        assert r.status_code == 503


def test_operator_live_rejects_non_localhost_when_token_unset():
    with TestClient(app, client=REMOTE) as client:
        r = client.post("/api/operator/live", json={})
        assert r.status_code == 503


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/operator/status", "get"),
        ("/api/operator-control/next-proof-candidate", "get"),
        ("/api/operator-control/external-prereqs/adapter/validate", "post"),
        ("/api/operator-control/external-prereqs/adapter/smoke", "post"),
        ("/api/operator-control/external-prereqs/live-submit/preview", "post"),
        ("/api/operator-control/external-prereqs/caps/preview", "post"),
    ],
)
def test_entire_operator_router_requires_auth_when_token_unset(path, method):
    with TestClient(app, client=LOCALHOST) as client:
        response = client.post(path, json={}) if method == "post" else client.get(path)
        assert response.status_code == 503, f"{path} returned {response.status_code}"


# --- Token set: bearer / X-Operator-Token required from any caller ----------

def test_valid_bearer_token_accepted(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s3cret")
    with TestClient(app, client=REMOTE) as client:
        r = client.post(
            "/emergency-stop",
            headers={"Authorization": "Bearer s3cret"},
        )
        assert r.status_code == 200


def test_valid_x_operator_token_accepted(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s3cret")
    with TestClient(app, client=REMOTE) as client:
        r = client.post(
            "/emergency-stop",
            headers={"X-Operator-Token": "s3cret"},
        )
        assert r.status_code == 200


def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s3cret")
    with TestClient(app, client=REMOTE) as client:
        r = client.post(
            "/emergency-stop",
            headers={"Authorization": "Bearer wrong"},
        )
        assert r.status_code == 403


def test_localhost_without_token_rejected_when_token_set(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s3cret")
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post("/emergency-stop")
        assert r.status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        # Non-ASCII header bytes must fail closed with 403, not TypeError -> 500.
        {"X-Operator-Token": "töken".encode("utf-8")},
        {"Authorization": "Bearer töken".encode("utf-8")},
    ],
)
def test_non_ascii_token_header_rejected_with_403_not_500(monkeypatch, headers):
    monkeypatch.setenv(ENV_VAR, "s3cret")
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post("/emergency-stop", headers=headers)
        assert r.status_code == 403


# --- Extension: remaining risk-increasing mutating POSTs are guarded --------

NEWLY_GUARDED_ROUTES = [
    "/api/operator-control/external-prereqs/caps/write",
    "/api/operator-control/external-prereqs/live-submit/disable",
    "/api/operator-control/second-proof-authority/activate",
    "/repo-harvester/run",
]


@pytest.mark.parametrize("path", NEWLY_GUARDED_ROUTES)
def test_newly_guarded_route_rejects_non_localhost_when_token_unset(path):
    with TestClient(app, client=REMOTE) as client:
        r = client.post(path, json={})
        assert r.status_code == 503, f"{path} returned {r.status_code}"


def test_caps_write_rejects_localhost_when_token_unset():
    with TestClient(app, client=LOCALHOST) as client:
        # Empty body fails the typed-confirmation check -> no file write, 200.
        r = client.post("/api/operator-control/external-prereqs/caps/write", json={})
        assert r.status_code == 503


def test_live_submit_disable_rejects_localhost_when_token_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dashboard.backend.operator_control_routes.LIVE_SUBMIT_PATH",
        tmp_path / "live_submit.json",
    )
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post("/api/operator-control/external-prereqs/live-submit/disable")
        assert r.status_code == 503


def test_second_proof_authority_activate_rejects_localhost_when_token_unset():
    with TestClient(app, client=LOCALHOST) as client:
        # Empty confirm fails the confirmation check -> no write, 200.
        r = client.post("/api/operator-control/second-proof-authority/activate", json={})
        assert r.status_code == 503


def test_repo_harvester_run_rejects_localhost_when_token_unset(monkeypatch):
    async def _noop_harvest():
        return None

    monkeypatch.setattr("dashboard.backend.main.run_harvester", _noop_harvest)
    with TestClient(app, client=LOCALHOST) as client:
        r = client.post("/repo-harvester/run")
        assert r.status_code == 503


# --- Bind default ------------------------------------------------------------

def test_uvicorn_launch_defaults_to_localhost():
    import runpy
    import sys
    from unittest.mock import patch

    recorded = {}

    def fake_run(app, host=None, port=None, log_level=None):
        recorded["host"] = host
        recorded["port"] = port

    with patch.dict(sys.modules, {"uvicorn": type(sys)("uvicorn")}):
        sys.modules["uvicorn"].run = fake_run
        runpy.run_path("main.py", run_name="__main__")

    assert recorded["host"] == "127.0.0.1"
    assert recorded["port"] == 8000
