"""Tests for Dashboard V4 backend endpoints."""

import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import app
from strategies.registry import ACTIVE_REPO_DERIVED_FAMILY_COUNT

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_kalshi_credentials(monkeypatch):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_v4_kalshi_status():
    r = client.get("/v4/kalshi/status")
    assert r.status_code == 200
    data = r.json()
    assert "connected" in data
    assert "credentials_present" in data


def test_v4_caps():
    r = client.get("/v4/caps")
    assert r.status_code == 200
    data = r.json()
    assert "max_single_order_cents" in data["caps"]


def test_v4_live_submit_status():
    r = client.get("/v4/live-submit/status")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert data["enabled"] is False


def test_v4_missing_credentials_never_fabricate_broker_state():
    account = client.get("/v4/kalshi/account").json()
    markets = client.get("/v4/kalshi/markets").json()
    orderbook = client.get("/v4/kalshi/orderbook/KXRAIN-DEMO").json()

    assert account["account"] is None
    assert account["source"] != "mock"
    assert markets["markets"] is None
    assert markets["events"] is None
    assert markets["source"] != "mock"
    assert orderbook["orderbook"] is None
    assert orderbook["source"] != "mock"
    assert orderbook["target_policy"]["role"] == "data_only"


def test_v4_strategies_scan():
    r = client.get("/v4/strategies/scan")
    assert r.status_code == 200
    data = r.json()
    assert len(data["scan_results"]) == ACTIVE_REPO_DERIVED_FAMILY_COUNT == 5
    families = {row["family"] for row in data["scan_results"]}
    assert not any("weather" in family or "commod" in family for family in families)
    assert "stock_macro_momentum" not in families
    assert data["source"] == "demo"
    assert data["data_status"] == "synthetic_orderbook"


def test_v4_firewall_blocked():
    r = client.get("/v4/firewall/blocked")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "local_log_derived"
    assert isinstance(data["observed_reasons"], list)
    assert data["observed_rejection_count"] == sum(
        item["count"] for item in data["observed_reasons"]
    )


def test_v4_firewall_rehearse_blocks_when_not_autonomous(monkeypatch):
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", "archive-test-token")
    r = client.get(
        "/v4/firewall/rehearse",
        headers={"Authorization": "Bearer archive-test-token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "blocked"
