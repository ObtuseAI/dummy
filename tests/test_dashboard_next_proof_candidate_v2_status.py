import json

import pytest
from fastapi.testclient import TestClient

from dashboard.backend import operator_control_routes as routes
from dashboard.backend.main import app


@pytest.fixture
def client(monkeypatch):
    token = "next-proof-v2-test-operator"
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", token)
    with TestClient(app, headers={"X-Operator-Token": token}) as authenticated:
        yield authenticated


def test_next_proof_candidate_returns_200(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    assert response.status_code == 200
    data = response.json()
    assert "v1_status" in data
    assert "v2_status" in data


def test_v2_status_appears_when_artifact_exists(client, tmp_path, monkeypatch):
    v2_path = tmp_path / "VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json"
    v2_path.write_text(
        json.dumps(
            {
                "candidate_found": True,
                "market_ticker": "KXBTC-26DEC25000-C",
                "contract_ticker": "KXBTC-26DEC25000-C",
                "market_tradable": True,
                "contract_tradable": True,
                "price_validated": True,
                "price_source": "kalshi_min_price",
                "price": 1,
                "read_only_metadata_contact": True,
                "api_key": "this_secret_must_not_be_returned",
            }
        )
    )
    monkeypatch.setattr(routes, "V2_CANDIDATE_PATH", v2_path)
    monkeypatch.setattr(routes, "V2_REPORT_PATH", tmp_path / "no_report.json")

    response = client.get("/api/operator-control/next-proof-candidate")
    assert response.status_code == 200
    data = response.json()
    v2 = data["v2_status"]

    assert v2["candidate_found"] is True
    assert v2["market_ticker"] == "KXBTC-26DEC25000-C"
    assert v2["contract_ticker"] == "KXBTC-26DEC25000-C"
    assert v2["market_tradable"] is True
    assert v2["contract_tradable"] is True
    assert v2["price_validated"] is True
    assert v2["price_source"] == "kalshi_min_price"
    assert v2["price"] == 1
    assert v2["read_only_metadata_contact"] is True
    assert v2["submit_allowed_now"] is False
    assert v2["requires_new_operator_proof_authority"] is True
    assert v2["proof_lock_status"] == "consumed_by_real_broker_attempt"
    assert v2["next_action"] == "review candidate; create new proof authority only if operator accepts"
    assert v2["no_submit_button"] is True
    assert v2["no_live_submit_auto_enable"] is True
    assert v2["secrets_redacted"] is True


def test_v2_status_not_generated_yet_when_artifact_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "V2_CANDIDATE_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(routes, "V2_REPORT_PATH", tmp_path / "missing_report.json")

    response = client.get("/api/operator-control/next-proof-candidate")
    assert response.status_code == 200
    v2 = response.json()["v2_status"]
    assert v2.get("status") == "not_generated_yet"
    assert v2["candidate_found"] is False
    assert v2["submit_allowed_now"] is False
    assert v2["no_submit_button"] is True
    assert v2["no_live_submit_auto_enable"] is True


def test_no_secrets_in_response(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    text = json.dumps(response.json()).lower()
    # "secrets_redacted" is an explicit safety flag, not a leaked secret.
    for forbidden in (
        "idempotency",
        "api_key",
        "apikey",
        "api_secret",
        "private_key",
        "password",
        "token",
    ):
        assert forbidden not in text, f"forbidden token '{forbidden}' leaked into response"


def test_no_submit_action_in_response(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    text = json.dumps(response.json()).lower()
    assert "one-shot-live" not in text
    assert "submit_order" not in text
    assert "execute-once" not in text
    assert "create_order" not in text


def test_submit_allowed_now_is_false(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    data = response.json()
    assert data["submit_allowed_now"] is False
    assert data["v2_status"]["submit_allowed_now"] is False
