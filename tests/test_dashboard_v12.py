from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


ENDPOINTS = [
    "/api/v12/orderbook-snapshot",
    "/api/v12/liquidity-replay",
    "/api/v12/liquidity-proof-v2",
    "/api/v12/fill-quality-v2",
    "/api/v12/stale-quote-risk-v2",
    "/api/v12/liquidity-calibration",
    "/api/v12/source-adapter-closure",
    "/api/v12/liquidity-bloodlines",
]


def test_v12_dashboard_endpoints_return_200() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"


def test_v12_dashboard_does_not_expose_secrets_or_prompts() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        text = client.get(endpoint).text
        assert "sk-" not in text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in text.lower()
