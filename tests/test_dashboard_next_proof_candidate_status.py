import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import app


@pytest.fixture
def client(monkeypatch):
    token = "next-proof-status-test-operator"
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", token)
    with TestClient(app, headers={"X-Operator-Token": token}) as authenticated:
        yield authenticated


def test_next_proof_candidate_status_no_secrets(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    assert response.status_code == 200
    data = response.json()
    assert "idempotency" not in str(data).lower()
    assert data["submit_allowed_now"] is False
    assert "requires_new_operator_proof_authority" in data
