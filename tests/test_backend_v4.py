"""Tests for Dashboard V4 backend endpoints."""

from fastapi.testclient import TestClient

from dashboard.backend.main import app

client = TestClient(app)


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


def test_v4_strategies_scan():
    r = client.get("/v4/strategies/scan")
    assert r.status_code == 200
    data = r.json()
    assert len(data["scan_results"]) == 8


def test_v4_firewall_blocked():
    r = client.get("/v4/firewall/blocked")
    assert r.status_code == 200
    data = r.json()
    assert "live_submit_disabled" in data["blocked_reasons"]


def test_v4_firewall_rehearse_blocks_when_not_autonomous():
    r = client.get("/v4/firewall/rehearse")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "blocked"
