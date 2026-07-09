from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


ENDPOINTS = [
    "/api/v13/kalshi-credential-bridge",
    "/api/v13/market-discovery",
    "/api/v13/orderbook-snapshot",
    "/api/v13/orderbook-replay",
    "/api/v13/liquidity-terrain",
    "/api/v13/kalshi-repair-packet",
    "/api/v13/source-adapter-closure",
    "/api/v13/test-runtime-profile",
]


def test_v13_dashboard_endpoints_return_redacted_statuses() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        text = response.text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in text.lower()
