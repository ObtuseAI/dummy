from fastapi.testclient import TestClient

from dashboard.backend.main import app

V3_ENDPOINTS = [
    "/v3/adapters",
    "/v3/adapters/pending",
    "/v3/adapters/rejected",
    "/v3/kalshi/status",
    "/v3/kalshi/markets",
    "/v3/kalshi/orderbook/WEATHER-NYC-RAIN-YES",
    "/v3/strategies/candidates",
    "/v3/proposed-trades",
    "/v3/blocked-orders",
    "/v3/firewall/verdicts",
    "/v3/caps",
    "/v3/exposure",
]


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
        r = client.get("/v3/kalshi/orderbook/WEATHER-NYC-RAIN-YES")
        assert r.status_code == 200
        data = r.json()
        assert "orderbook" in data
        book = data["orderbook"]
        assert "bids" in book
        assert "asks" in book


def test_v3_strategies_candidates():
    with TestClient(app) as client:
        r = client.get("/v3/strategies/candidates")
        assert r.status_code == 200
        data = r.json()
        assert "candidates" in data
        assert "registered_strategies" in data
        assert isinstance(data["registered_strategies"], list)


def test_v3_proposed_trades():
    with TestClient(app) as client:
        r = client.get("/v3/proposed-trades")
        assert r.status_code == 200
        data = r.json()
        assert "proposals" in data
        assert "market_ticker" in data
        assert "contract_ticker" in data


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


def test_existing_endpoints_still_work():
    with TestClient(app) as client:
        for ep in ["/status", "/markets", "/forecasts", "/risk"]:
            r = client.get(ep)
            assert r.status_code == 200, f"existing {ep} returned {r.status_code}"
