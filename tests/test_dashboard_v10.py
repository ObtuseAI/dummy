from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


ENDPOINTS = [
    "/api/v10/build-factory",
    "/api/v10/build-queue",
    "/api/v10/validation-shards",
    "/api/v10/source-adapters",
    "/api/v10/edge-accelerator",
    "/api/v10/bloodlines",
    "/api/v10/mesh-throughput",
    "/api/v10/progress-score",
]


def test_v10_dashboard_endpoints_return_200() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, f"{endpoint}: {response.text}"


def test_v10_dashboard_does_not_expose_secrets_or_prompts() -> None:
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        text = response_text = client.get(endpoint).text
        assert "sk-" not in text
        assert "BEGIN PRIVATE KEY" not in text
        assert "raw_prompt" not in response_text.lower()


def test_v10_dashboard_build_factory_shape() -> None:
    client = TestClient(app)
    data = client.get("/api/v10/build-factory").json()
    assert data["verdict"] == "PASS"
    assert data["packet_count"] > 0
    assert data["live_submit_disabled"] is True
