from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app

ENDPOINTS = [
    "/api/v15/credential-shape-repair",
    "/api/v15/credential-source-conflicts",
    "/api/v15/normalization-preview",
    "/api/v15/auth-probe-v2",
    "/api/v15/real-terrain-retry-v2",
    "/api/v15/real-orderbook-terrain-v3",
    "/api/v15/liquidity-launch-gate-v2",
    "/api/v15/source-adapter-closure-v5",
    "/api/v15/runtime-acceleration-v2",
]


def test_v15_dashboard_endpoints_return_redacted_statuses() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        text = response.text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in text.lower()
        assert "account_balance" not in text.lower()


def test_v15_endpoints_report_live_submit_disabled() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS[:-1]:
        response = client.get(endpoint)
        assert response.json().get("live_submit_disabled") is True
