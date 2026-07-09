from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend import v14_routes
from dashboard.backend.main import app
from predator_mesh.v13.market_discovery import MarketDiscoveryMode, MarketDiscoveryProof
from predator_mesh.v13.orderbook_snapshot_v2 import RealOrderbookSnapshotClosure
from tests.v14_test_helpers import fake_valid_forensics_report, real_snapshot_result


ENDPOINTS = [
    "/api/v14/kalshi-forensics",
    "/api/v14/kalshi-repair-wizard",
    "/api/v14/real-terrain-retry",
    "/api/v14/real-terrain-closure",
    "/api/v14/source-adapter-promotion",
    "/api/v14/liquidity-launch-readiness",
    "/api/v14/micro-order-dry-run",
    "/api/v14/liquidity-no-trade-gates",
    "/api/v14/runtime-acceleration",
]


def test_v14_dashboard_endpoints_return_redacted_statuses() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        text = response.text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in text.lower()
        assert "account_balance" not in text.lower()


def test_v14_dashboard_real_terrain_endpoint_uses_async_capture_when_credentials_valid(monkeypatch) -> None:
    closure = RealOrderbookSnapshotClosure(
        real_snapshot_result(),
        MarketDiscoveryProof(
            mode=MarketDiscoveryMode.REAL_READ_ONLY_DISCOVERY,
            eligible_candidates=[],
            real_read_only_used=True,
        ),
        "REAL_READ_ONLY",
        {"ready": True, "redacted": True},
    )

    async def fake_capture(self):
        return closure

    monkeypatch.setattr(v14_routes, "_forensics", fake_valid_forensics_report)
    monkeypatch.setattr("predator_mesh.v14.terrain_closure.RealKalshiOrderbookSnapshotAdapterV2.capture", fake_capture)

    response = TestClient(app).get("/api/v14/real-terrain-closure")

    assert response.status_code == 200, response.text
    assert response.json()["snapshot"]["outcome"] == "REAL_READ_ONLY"
