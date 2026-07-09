from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_dashboard_v16_mission_state_endpoint_returns_redacted_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v16/mission-state")

    assert response.status_code == 200, response.text
    text = response.text
    assert "BEGIN PRIVATE KEY" not in text
    assert "raw_prompt" not in text.lower()
    assert "mission_state" in response.json()
