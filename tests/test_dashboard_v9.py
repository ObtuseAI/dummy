from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from predator_mesh.models import LaneState, MeshBudget, MeshRun, MeshResult
from predator_mesh.proof_ledger import MeshProofLedger


async def _mock_run_cycle(ledger: MeshProofLedger | None = None) -> tuple[MeshRun, MeshProofLedger]:
    """Lightweight deterministic mesh cycle for dashboard tests."""
    ledger = ledger or MeshProofLedger()
    ledger.record(event="lane_started", lane="mock_lane")
    ledger.record(event="lane_completed", lane="mock_lane")
    run = MeshRun(
        run_id="mock-run-id",
        state=LaneState.COMPLETED,
        budget_used=MeshBudget(),
    )
    run.lane_results = [
        MeshResult(
            lane_name="mock_lane",
            state=LaneState.COMPLETED,
            events_recorded=2,
        )
    ]
    return run, ledger


ENDPOINTS = [
    "/api/v9/mesh/status",
    "/api/v9/mesh/lanes",
    "/api/v9/data-inflow/sources",
    "/api/v9/signals",
    "/api/v9/edges",
    "/api/v9/aggression-governor",
    "/api/v9/mesh-health",
    "/api/v9/proof",
]


def test_v9_routes_return_200():
    client = TestClient(app)
    with patch("dashboard.backend.v9_routes._run_mesh_cycle", new=_mock_run_cycle):
        for ep in ENDPOINTS:
            r = client.get(ep)
            assert r.status_code == 200, f"{ep} failed: {r.text}"


def test_v9_routes_contain_no_secrets():
    client = TestClient(app)
    with patch("dashboard.backend.v9_routes._run_mesh_cycle", new=_mock_run_cycle):
        for ep in ENDPOINTS:
            r = client.get(ep)
            assert r.status_code == 200, f"{ep} failed: {r.text}"
            text = str(r.json())
            assert "sk-" not in text, f"{ep} leaked sk- token"
            assert "BEGIN" not in text, f"{ep} leaked PEM block"
            assert "api_key" not in text.lower(), f"{ep} leaked api_key"


def test_v9_mesh_status_shape():
    client = TestClient(app)
    with patch("dashboard.backend.v9_routes._run_mesh_cycle", new=_mock_run_cycle):
        r = client.get("/api/v9/mesh/status")
    assert r.status_code == 200
    data = r.json()
    assert data["project"] == "Dummy"
    assert data["milestone"] == "DUMMY_V9_CONCURRENT_PREDATOR_MESH"
    assert "mode" in data
    assert "lane_count" in data
    assert "lanes" in data
    assert data["lane_count"] == 1
    assert data["lanes"][0]["lane_name"] == "mock_lane"


def test_v9_mesh_lanes_shape():
    client = TestClient(app)
    r = client.get("/api/v9/mesh/lanes")
    assert r.status_code == 200
    data = r.json()
    assert data["lane_count"] > 0
    names = {lane["name"] for lane in data["lanes"]}
    assert "kalshi_terrain" in names
    assert "recursive_inflow" in names


def test_v9_data_inflow_sources_shape():
    client = TestClient(app)
    r = client.get("/api/v9/data-inflow/sources")
    assert r.status_code == 200
    data = r.json()
    assert data["source_count"] > 0
    assert "sources" in data
    for source in data["sources"]:
        assert "source_id" in source
        assert "name" in source
        assert "category" in source


def test_v9_signals_shape():
    client = TestClient(app)
    r = client.get("/api/v9/signals")
    assert r.status_code == 200
    data = r.json()
    assert "signal_count" in data
    assert "signals" in data
    for signal in data["signals"]:
        assert "signal_type" in signal
        assert "source_id" in signal


def test_v9_edges_shape():
    client = TestClient(app)
    r = client.get("/api/v9/edges")
    assert r.status_code == 200
    data = r.json()
    assert "candidate_count" in data
    assert "candidates" in data
    for candidate in data["candidates"]:
        assert "candidate_id" in candidate
        assert "decision" in candidate


def test_v9_aggression_governor_shape():
    client = TestClient(app)
    r = client.get("/api/v9/aggression-governor")
    assert r.status_code == 200
    data = r.json()
    assert "decision" in data
    assert "size_pct" in data
    assert "confidence" in data
    assert "proof_reference" in data


def test_v9_mesh_health_shape():
    client = TestClient(app)
    with patch("dashboard.backend.v9_routes._run_mesh_cycle", new=_mock_run_cycle):
        r = client.get("/api/v9/mesh-health")
    assert r.status_code == 200
    data = r.json()
    assert "healthy" in data
    assert "event_count" in data
    assert "slow_lanes" in data
    assert "stuck_lanes" in data


def test_v9_proof_shape():
    client = TestClient(app)
    with patch("dashboard.backend.v9_routes._run_mesh_cycle", new=_mock_run_cycle):
        r = client.get("/api/v9/proof")
    assert r.status_code == 200
    data = r.json()
    assert "report" in data
    assert data["report"]["report_type"] == "mesh_proof_ledger_report_v1"
    assert data["report"]["event_count"] > 0
