from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from dashboard.backend.main import app
from dashboard.backend.vnext_routes import observatory, observatory_panel, router
from dummy.observatory import ObservatoryPanel


def test_checked_in_observatory_has_all_panels_and_evidence_links() -> None:
    snapshot = observatory()
    assert snapshot["authority"] == "OBSERVE"
    assert snapshot["read_only"] is True
    assert snapshot["write_actions"] == []
    assert snapshot["execution_authority"] is False
    assert snapshot["telemetry_status"] == "POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY"
    assert {item["panel"] for item in snapshot["panels"]} == {
        item.value for item in ObservatoryPanel
    }
    for panel in snapshot["panels"]:
        assert panel["claims"]
        assert all(claim["evidence_ids"] for claim in panel["claims"])


def test_observatory_router_exposes_get_only_surfaces() -> None:
    assert router.routes
    assert all(route.methods == {"GET"} for route in router.routes)
    assert observatory_panel("constitution")["panel"] == "constitution"
    with pytest.raises(HTTPException) as exc_info:
        observatory_panel("not-a-panel")
    assert exc_info.value.status_code == 404


def test_main_dashboard_mounts_only_get_vnext_routes() -> None:
    assert any(getattr(route, "original_router", None) is router for route in app.routes)
    assert {route.path for route in router.routes} == {
        "/api/vnext/observatory",
        "/api/vnext/observatory/{panel_name}",
        "/api/vnext/arenas",
        "/api/vnext/arena-catalog",
        "/api/vnext/homeostasis",
    }
    assert all(route.methods == {"GET"} for route in router.routes)

    response = TestClient(app).get("/api/vnext/observatory")
    assert response.status_code == 200
    assert response.json()["authority"] == "OBSERVE"


def test_observatory_frontend_is_first_class_and_read_only() -> None:
    app = Path("dashboard/frontend/src/App.jsx").read_text(encoding="utf-8")
    page = Path("dashboard/frontend/src/VNextObservatory.jsx").read_text(
        encoding="utf-8"
    )
    assert "vNext Observatory" in app
    assert 'path="/vnext-observatory"' in app
    assert "fetch('/api/vnext/observatory')" in page
    assert "fetch(" in page
    assert not any(method in page for method in ("POST", "PUT", "PATCH", "DELETE"))


def test_phase7_audit_is_byte_deterministic_and_honest(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase7_audit.py"
    command = [sys.executable, str(script), "--output-dir", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    assert first == second
    arena = json.loads(first["VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json"])
    snapshot = json.loads(first["VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json"])
    assert arena["status"] == "MECHANICS_VALIDATED_NO_EMPIRICAL_CLAIM"
    assert arena["runtime_episode_count"] == 0
    assert snapshot["telemetry_status"] == "POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY"
