from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


ENDPOINTS = [
    "/api/v11/liquidity-proof",
    "/api/v11/orderbook-liquidity",
    "/api/v11/fill-quality",
    "/api/v11/shadow-orders",
    "/api/v11/micro-order-arming",
    "/api/v11/cancel-reconcile",
    "/api/v11/order-lifecycle",
    "/api/v11/liquidity-aggression",
    "/api/v11/post-trade-ledger",
]


def test_v11_dashboard_endpoints_return_200() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"


def test_v11_dashboard_does_not_expose_secrets_or_prompts() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        text = client.get(endpoint).text
        assert "sk-" not in text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in text.lower()


def test_v11_dashboard_liquidity_proof_shape() -> None:
    data = TestClient(app).get("/api/v11/liquidity-proof").json()

    assert data["verdict"] == "PASS"
    assert data["live_submit_disabled"] is True
    assert data["firewall_rehearsal_status"] == "BLOCKED_LIVE_SUBMIT_DISABLED"
