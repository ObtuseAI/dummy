import asyncio

import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import app
from archive.routes import v3_routes

V3_ENDPOINTS = [
    "/v3/adapters",
    "/v3/adapters/pending",
    "/v3/adapters/rejected",
    "/v3/kalshi/status",
    "/v3/kalshi/markets",
    "/v3/kalshi/orderbook/SPORTS-DEMO-MATCHUP-HOME",
    "/v3/strategies/candidates",
    "/v3/proposed-trades",
    "/v3/blocked-orders",
    "/v3/firewall/verdicts",
    "/v3/caps",
    "/v3/exposure",
]


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


def test_v3_endpoints_exist_and_ok():
    with TestClient(app) as client:
        for ep in V3_ENDPOINTS:
            r = client.get(ep)
            assert r.status_code == 200, f"{ep} returned {r.status_code}: {r.text}"


def test_v3_adapters_counts():
    with TestClient(app) as client:
        r = client.get("/v3/adapters")
        assert r.status_code == 200
        data = r.json()
        assert "accepted" in data
        assert "pending" in data
        assert "rejected" in data
        assert "counts" in data
        assert data["counts"]["accepted"] >= 0
        assert data["counts"]["rejected"] >= 0


def test_v3_kalshi_status_no_secrets():
    with TestClient(app) as client:
        r = client.get("/v3/kalshi/status")
        assert r.status_code == 200
        data = r.json()
        assert "connected" in data
        assert "api_key_id_present" in data
        # Secrets must be redacted; raw private key should never appear.
        text = r.text
        assert "KALSHI_API_PRIVATE_KEY" not in text


def test_v3_kalshi_orderbook_shape():
    with TestClient(app) as client:
        r = client.get("/v3/kalshi/orderbook/SPORTS-DEMO-MATCHUP-HOME")
        assert r.status_code == 200
        data = r.json()
        assert "orderbook" in data
        assert data["orderbook"] is None
        assert data["data_status"] == "unavailable"
        assert data["target_policy"]["role"] == "eligibility_unverified"


def test_v3_missing_credentials_never_fabricate_markets_or_books():
    with TestClient(app) as client:
        markets = client.get("/v3/kalshi/markets").json()
        book = client.get("/v3/kalshi/orderbook/KXRAIN-DEMO").json()

    assert markets["events"] is None
    assert markets["source"] != "mock"
    assert book["orderbook"] is None
    assert book["source"] != "mock"
    assert book["target_policy"] == {
        "role": "data_only",
        "prediction_target": False,
        "execution_target": False,
    }


def test_v3_strategies_candidates():
    with TestClient(app) as client:
        r = client.get("/v3/strategies/candidates")
        assert r.status_code == 200
        data = r.json()
        assert "candidates" in data
        assert "registered_strategies" in data
        assert isinstance(data["registered_strategies"], list)


def test_v3_strategy_candidates_label_unknown_and_thin_data(monkeypatch):
    monkeypatch.setattr(
        v3_routes,
        "_load_artifact",
        lambda _filename: {
            "candidates": [
                {"strategy_name": "SmallSample", "sample_size": 12},
                {"strategy_name": "Unmeasured", "sample_size": "unknown"},
                {"strategy_name": "Measured", "sample_size": 30},
            ]
        },
    )

    data = asyncio.run(v3_routes.strategies_candidates())

    assert [candidate["thin_data"] for candidate in data["candidates"]] == [True, True, False]
    assert all(candidate["validation_status"] == "UNKNOWN" for candidate in data["candidates"])


def test_v3_proposed_trades():
    with TestClient(app) as client:
        r = client.get("/v3/proposed-trades")
        assert r.status_code == 200
        data = r.json()
        assert "proposals" in data
        assert "market_ticker" in data
        assert "contract_ticker" in data
        assert data["source"] == "demo"
        assert data["data_status"] == "synthetic_orderbook"


def test_v3_caps_read_only():
    with TestClient(app) as client:
        r = client.get("/v3/caps")
        assert r.status_code == 200
        data = r.json()
        assert "caps" in data
        assert data["source"] == "configs/caps.json"
        assert data["caps"]["limit_orders_only"] is True


def test_v3_exposure():
    with TestClient(app) as client:
        r = client.get("/v3/exposure")
        assert r.status_code == 200
        data = r.json()
        assert "positions" in data
        assert "total_exposure_cents" in data
        assert "open_markets" in data
        assert "orders_last_hour" in data
        assert data["orders_last_hour_window"] == "rolling_60_minutes_utc"


def test_existing_endpoints_still_work():
    with TestClient(app) as client:
        for ep in ["/status", "/markets", "/forecasts", "/risk"]:
            r = client.get(ep)
            assert r.status_code == 200, f"existing {ep} returned {r.status_code}"
