"""Production React/API truth contract: local reads only, UNKNOWN over invention."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.backend import read_only_routes as read_only
from dashboard.backend.main import app


ROOT = Path(__file__).resolve().parents[1]


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


@pytest.mark.asyncio
async def test_production_kalshi_reads_never_fabricate_missing_live_state():
    status = await read_only.kalshi_status()
    markets = await read_only.kalshi_markets()
    book = await read_only.kalshi_orderbook("KXRAIN-DEMO")
    fills = await read_only.kalshi_fills()

    assert status["connected"] is False
    assert status["connection_verified"] is False
    assert status["connection_witness_at"] is None
    assert markets["events"] is None
    assert markets["markets"] is None
    assert book["orderbook"] is None
    assert fills["fills"] is None
    assert all(payload["source"] != "mock" for payload in (status, markets, book, fills))
    assert book["target_policy"] == {
        "role": "data_only",
        "prediction_target": False,
        "execution_target": False,
    }


@pytest.mark.asyncio
async def test_exposure_reports_rolling_hour_metric_separately(monkeypatch):
    class Position:
        def model_dump(self, mode="json"):
            return {"contract_ticker": "SPORTS-ONE", "quantity": 1}

    class Tracker:
        state_healthy = True
        persistence_error = None
        positions = {("SPORTS-ONE", "yes"): Position()}
        open_orders = [{"order_id": "o1"}, {"order_id": "o2"}]

        def total_exposure_cents(self):
            return 75

        def open_markets(self):
            return 1

        def open_order_count(self):
            return 2

        def orders_last_hour(self):
            return 5

    monkeypatch.setattr(read_only, "get_persistent_exposure_tracker", lambda: Tracker())

    result = await read_only.exposure()

    assert result["open_order_count"] == 2
    assert result["orders_last_hour"] == 5
    assert result["orders_last_hour_window"] == "rolling_60_minutes_utc"


@pytest.mark.asyncio
async def test_live_submit_config_is_not_presented_as_execution_authority(tmp_path, monkeypatch):
    path = tmp_path / "live_submit.json"
    path.write_text(json.dumps({"enabled": True}), encoding="utf-8")
    monkeypatch.setattr(read_only, "LIVE_SUBMIT_PATH", path)

    result = await read_only.live_submit_status()

    assert result["configured_enabled"] is True
    assert result["effective_execution_enabled"] is None
    assert result["enabled"] is None
    assert result["execution_authority"] is False
    assert result["validation_status"] == "VALID_CONFIG_ONLY"


@pytest.mark.asyncio
async def test_missing_firewall_log_is_unknown_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(read_only, "LOG_FILE", tmp_path / "missing.jsonl")

    result = await read_only.firewall_rejections()

    assert result["data_status"] == "unavailable"
    assert result["observed_reasons"] is None
    assert result["observed_rejection_count"] is None
    assert result["firewall_events_scanned"] is None
    assert result["unavailable_reason"] == "local_firewall_log_missing"


def test_operator_token_probe_is_usable_and_never_returns_secret(monkeypatch):
    monkeypatch.setenv("DUMMY_OPERATOR_TOKEN", "do-not-display-this-token")
    with TestClient(app) as client:
        locked = client.get("/operator-auth/status")
        unlocked = client.get(
            "/operator-auth/status",
            headers={"Authorization": "Bearer do-not-display-this-token"},
        )

    assert locked.status_code == 200
    assert locked.json()["configured"] is True
    assert locked.json()["authenticated"] is False
    assert unlocked.json()["authenticated"] is True
    assert unlocked.json()["secret_returned"] is False
    assert "do-not-display-this-token" not in locked.text + unlocked.text


def test_active_read_only_routes_are_mounted_and_fail_closed():
    """Guard the production UI contract at the HTTP boundary, not just helpers."""
    with TestClient(app) as client:
        responses = {
            path: client.get(path)
            for path in (
                "/api/read-only/caps",
                "/api/read-only/exposure",
                "/api/read-only/kalshi/status",
                "/api/read-only/kalshi/markets",
                "/api/read-only/kalshi/orderbook/KXRAIN-DEMO",
                "/api/read-only/kalshi/account",
                "/api/read-only/kalshi/positions",
                "/api/read-only/kalshi/orders",
                "/api/read-only/kalshi/fills",
                "/api/read-only/firewall/rejections",
                "/api/read-only/firewall/rehearsal",
                "/api/read-only/live-submit/status",
                "/api/read-only/model-panel",
            )
        }

    assert all(response.status_code == 200 for response in responses.values())
    assert responses["/api/read-only/kalshi/markets"].json()["markets"] is None
    assert responses["/api/read-only/kalshi/orderbook/KXRAIN-DEMO"].json()["orderbook"] is None
    assert responses["/api/read-only/kalshi/fills"].json()["fills"] is None
    rehearsal = responses["/api/read-only/firewall/rehearsal"].json()
    assert rehearsal["rehearsal_executed"] is False
    assert rehearsal["status"] == "NOT_RUN_READ_ONLY_SURFACE"
    submit = responses["/api/read-only/live-submit/status"].json()
    assert submit["execution_authority"] is False
    model_panel = responses["/api/read-only/model-panel"].json()
    assert model_panel["provider_contacted_by_dashboard"] is False
    assert model_panel["network_action_available"] is False
    assert model_panel["authorities"] == {
        "evidence": False,
        "probability": False,
        "order": False,
    }


def test_read_only_router_has_no_broker_provider_process_or_write_client():
    source = inspect.getsource(read_only)
    forbidden = (
        "KalshiLiveData",
        "KalshiRealReadOnly",
        "import subprocess",
        "subprocess.",
        "create_order",
        "cancel_order",
        "model_router",
        "openrouter",
    )
    assert not any(token in source for token in forbidden)


def test_react_truth_contract_uses_unknown_and_active_read_only_routes():
    truth = (ROOT / "dashboard/frontend/src/components/TruthValue.js").read_text(encoding="utf-8")
    forecasts = (ROOT / "dashboard/frontend/src/screens/Forecasts.jsx").read_text(encoding="utf-8")
    home = (ROOT / "dashboard/frontend/src/screens/Home.jsx").read_text(encoding="utf-8")
    markets = (ROOT / "dashboard/frontend/src/screens/Markets.jsx").read_text(encoding="utf-8")
    caps = (ROOT / "dashboard/frontend/src/screens/CapsExposure.jsx").read_text(encoding="utf-8")
    kalshi = (ROOT / "dashboard/frontend/src/screens/Kalshi.jsx").read_text(encoding="utf-8")
    kalshi_real = (ROOT / "dashboard/frontend/src/screens/KalshiReal.jsx").read_text(encoding="utf-8")
    token_ui = (ROOT / "dashboard/frontend/src/screens/OperatorControl.jsx").read_text(encoding="utf-8")
    orders = (ROOT / "dashboard/frontend/src/screens/Orders.jsx").read_text(encoding="utf-8")
    positions = (ROOT / "dashboard/frontend/src/screens/Positions.jsx").read_text(encoding="utf-8")
    strategies = (ROOT / "dashboard/frontend/src/screens/Strategies.jsx").read_text(encoding="utf-8")
    logs = (ROOT / "dashboard/frontend/src/screens/Logs.jsx").read_text(encoding="utf-8")
    proof = (ROOT / "dashboard/frontend/src/screens/Proof.jsx").read_text(encoding="utf-8")
    vnext = (ROOT / "dashboard/frontend/src/VNextObservatory.jsx").read_text(encoding="utf-8")
    forecast_quality = (ROOT / "dashboard/frontend/src/components/ForecastQuality.jsx").read_text(encoding="utf-8")
    rehearsal = (ROOT / "dashboard/frontend/src/screens/FirewallRehearsal.jsx").read_text(encoding="utf-8")
    live_submit = (ROOT / "dashboard/frontend/src/screens/LiveSubmit.jsx").read_text(encoding="utf-8")
    model_panel = (ROOT / "dashboard/frontend/src/screens/ModelPanel.jsx").read_text(encoding="utf-8")
    app_source = (ROOT / "dashboard/frontend/src/App.jsx").read_text(encoding="utf-8")

    assert "return 'UNKNOWN'" in truth
    assert "/api/read-only/kalshi/status" in home
    assert "Broker connection verified" in home
    assert 'label="Kalshi Connected"' not in home
    assert "NO SETTLEMENT-BACKED PERFORMANCE CLAIM" in forecasts
    assert "stored forecast observations" in forecasts
    assert "Valuation evidence:" not in forecasts
    assert "Equity and index observations" not in forecasts
    assert "freshness_status" in forecasts
    assert "Stored target forecasts excluded" in forecasts
    assert "DATA_ONLY_TICKER_PREFIXES" in forecasts
    assert "Configuration only" in markets
    assert "Weather and commodities are data-only" in markets
    assert "orders_last_hour" in caps
    assert 'value={exposure.open_order_count} cap={capsData.max_orders_per_hour}' not in caps
    assert "/api/read-only/kalshi" in kalshi
    assert "/api/read-only/kalshi" in kalshi_real
    assert "Connection verified" in kalshi + kalshi_real
    assert "Connected (runtime witness)" not in kalshi + kalshi_real
    assert "WEATHER-NYC" not in kalshi + kalshi_real
    assert "Nothing is loaded automatically" in kalshi + kalshi_real
    assert "/operator-auth/status" in token_ui
    assert 'type="password"' in token_ui
    assert "Token matches backend" in token_ui
    assert "candidate_count || 1" not in token_ui
    assert "candidate_order_type || 'LIMIT'" not in token_ui
    assert "/api/read-only/kalshi/orders" in orders
    assert "/api/read-only/kalshi/positions" in positions
    assert "orders || []" not in orders
    assert "positions || []" not in positions
    assert "Stored research inventory only" in strategies
    assert "Data-only candidates excluded" in strategies
    assert "Log collection status: UNKNOWN" in logs
    assert "Authority granted" in proof
    assert "booleanLabel(promotion.transition_eligible" in vnext
    assert "arrayCountOrUnknown(promotion.blockers)" in vnext
    assert "snapshot.snapshot_id.slice" not in vnext
    assert "Forecast quality: UNKNOWN" in forecast_quality
    assert "value === null" in forecast_quality
    assert "observed_reasons || []" not in rehearsal
    assert "REHEARSAL EXECUTION STATUS UNKNOWN" in rehearsal
    assert "does not enable submission by itself" in live_submit
    assert "/api/read-only/model-panel" in model_panel
    assert "google/gemini-3.6-flash" in model_panel
    assert "openai/gpt-5.6-luna" in model_panel
    assert "anthropic/claude-sonnet-5" in model_panel
    assert "z-ai/glm-5.2" in model_panel
    assert "Persistent config gate" in model_panel
    assert "Runtime opt-in" in model_panel
    assert "Authority remains disabled" in model_panel
    assert "postJson" not in model_panel
    assert '<Route path="/model-panel" element={<ModelPanel />} />' in app_source
    assert "'Home','Model Panel','Operator Control'" in app_source
