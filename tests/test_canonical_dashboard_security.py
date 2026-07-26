from __future__ import annotations

import argparse
import inspect
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autonomy.dashboard import build_app
from scripts.run_dummy_dashboard import validate_loopback_host


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("host", ["127.0.0.1", "127.77.0.2", "::1", "localhost"])
def test_launcher_accepts_only_loopback_hosts(host):
    assert validate_loopback_host(host)


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.50", "100.64.0.10", "example.com", ""],
)
def test_launcher_rejects_remote_tailnet_and_wildcard_hosts(host):
    with pytest.raises(argparse.ArgumentTypeError):
        validate_loopback_host(host)


def test_canonical_app_rejects_remote_peer_even_with_local_host_header():
    with TestClient(build_app(), client=("203.0.113.10", 50000)) as client:
        response = client.get("/", headers={"Host": "127.0.0.1:8787"})

    assert response.status_code == 403
    assert response.json()["detail"].endswith("loopback only.")


def test_canonical_app_rejects_dns_rebinding_host_from_loopback_peer():
    with TestClient(build_app(), client=("127.0.0.1", 50000)) as client:
        response = client.get("/", headers={"Host": "attacker.example"})

    assert response.status_code == 403


def test_canonical_app_is_get_only_and_sets_browser_security_headers():
    app = build_app()
    methods = {
        method
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/", headers={"Host": "127.0.0.1:8787"})
        post = client.post(
            "/api/paper-scheduler/start",
            headers={"Host": "127.0.0.1:8787"},
        )

    assert methods <= {"GET", "HEAD"}
    assert post.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "connect-src 'self'" in response.headers["content-security-policy"]


def test_canonical_dashboard_module_has_no_ui_mutation_route():
    source = inspect.getsource(__import__("autonomy.dashboard", fromlist=["build_app"]))
    assert '@app.post(' not in source
    assert '@app.put(' not in source
    assert '@app.patch(' not in source
    assert '@app.delete(' not in source


def test_retired_dashboard_entrypoints_and_mutation_surface_are_absent():
    retired = (
        ROOT / "main.py",
        ROOT / "dashboard" / "__init__.py",
        ROOT / "dashboard" / "backend" / "__init__.py",
        ROOT / "dashboard" / "backend" / "main.py",
        ROOT / "adapters" / "fastapi_service.py",
        ROOT / "adapters" / "websocket_status_feed.py",
        ROOT / "scripts" / "validate.py",
        ROOT / "scripts" / "generate_reports.py",
    )
    assert not [str(path.relative_to(ROOT)) for path in retired if path.exists()]

    launcher = (ROOT / "scripts" / "run_dummy_dashboard.py").read_text(
        encoding="utf-8"
    )
    assert "from autonomy.dashboard import build_app" in launcher
    assert "dashboard.backend" not in launcher
