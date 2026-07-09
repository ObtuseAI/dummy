import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import state as state_module
from core.config_loader import load_caps
from core.ontology import (
    AccountMode,
    FirewallVerdict,
    LiveOrderResult,
    OrderBook,
    OrderBookLevel,
)
from execution.autonomous_path import (
    AutonomousExecutionPath,
    _source_has_create_order_call,
    generate_autonomous_live_capped_path_report,
    generate_firewall_order_path_report,
)
from forecasting.engine import ForecastEngine
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall
import live_firewall.firewall as firewall_module
import proof.ledger as proof_module


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    """Reset global state and redirect proof writes to a temp directory."""
    fresh = state_module.DummyState()
    state_module.STATE = fresh
    firewall_module.STATE = fresh
    monkeypatch.setattr(proof_module, "PROOF_DIR", tmp_path)
    os.environ["KALSHI_API_KEY_ID"] = "kalshi_test_key_12345"
    yield


def _make_book(
    bids: list[tuple[int, int]] | None = None,
    asks: list[tuple[int, int]] | None = None,
):
    bids = bids or [(48, 10)]
    asks = asks or [(52, 10)]
    return OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        bids=[OrderBookLevel(price=p, size=s) for p, s in bids],
        asks=[OrderBookLevel(price=p, size=s) for p, s in asks],
        timestamp=datetime.now(timezone.utc),
    )


def _caps_with_market():
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    return caps


@pytest.mark.asyncio
async def test_mode_gating_blocks_when_off():
    state_module.STATE.set_mode(AccountMode.OFF)
    path = AutonomousExecutionPath()
    result = await path.run_cycle("MARKET", "MARKET-YES")
    assert result["status"] == "blocked"
    assert result["rejected_by"] == "mode"
    assert "AUTONOMOUS_LIVE_CAPPED" in result["reason"]
    assert "proof_reference" in result


@pytest.mark.asyncio
async def test_mode_gating_blocks_when_read_only():
    state_module.STATE.set_mode(AccountMode.READ_ONLY)
    path = AutonomousExecutionPath()
    result = await path.run_cycle("MARKET", "MARKET-YES")
    assert result["status"] == "blocked"
    assert result["rejected_by"] == "mode"


@pytest.mark.asyncio
async def test_full_chain_success_with_real_firewall():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())
    live_data.get_resting_orders = AsyncMock(return_value={"orders": []})
    live_data.get_fills = AsyncMock(return_value={"fills": []})

    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "ord-123"}}

    exposure = ExposureTracker()
    firewall = LiveBrokerFirewall(client, exposure)

    caps = _caps_with_market()
    with patch("core.config_loader.load_caps", return_value=caps), patch(
        "live_firewall.firewall.load_caps", return_value=caps
    ), patch.object(
        LiveBrokerFirewall, "_live_submit_enabled", return_value=True
    ):
        path = AutonomousExecutionPath(
            live_data=live_data,
            firewall=firewall,
            exposure_tracker=exposure,
        )
        result = await path.run_cycle(
            "MARKET",
            "MARKET-YES",
            strategy_name="OrderbookSpreadCaptureStrategy",
        )

    assert result["status"] == "success"
    assert result["order_result"]["success"] is True
    assert result["order_result"]["order_id"] == "ord-123"
    assert result["proof_reference"]

    # LiveBrokerFirewall.submit is the only caller of create_order.
    client.create_order.assert_awaited_once()
    order = client.create_order.call_args[0][0]
    assert order["type"] == "limit"
    assert order["ticker"] == "MARKET-YES"
    assert order["side"] == "yes"
    assert order["count"] == 1


@pytest.mark.asyncio
async def test_full_chain_routes_through_mock_firewall():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())
    live_data.get_resting_orders = AsyncMock(return_value={"orders": []})
    live_data.get_fills = AsyncMock(return_value={"fills": []})

    firewall = AsyncMock()
    firewall.evaluate = AsyncMock(
        return_value=FirewallVerdict(allow=True, reason="mock pass")
    )
    firewall.submit = AsyncMock(
        return_value=LiveOrderResult(success=True, order_id="ord-mock", proof_reference="pref")
    )

    path = AutonomousExecutionPath(live_data=live_data, firewall=firewall)
    result = await path.run_cycle(
        "MARKET",
        "MARKET-YES",
        strategy_name="OrderbookSpreadCaptureStrategy",
    )

    assert result["status"] == "success"
    firewall.evaluate.assert_awaited_once()
    firewall.submit.assert_awaited_once()
    request = firewall.submit.call_args[0][0]
    assert request.market_ticker == "MARKET"
    assert request.contract_ticker == "MARKET-YES"
    assert request.side == "yes"
    assert request.adapter_name == "kalshi_live_firewall_adapter"
    assert request.strategy_proof_reference.startswith("strategy:")
    assert request.forecast_proof_reference.startswith("forecast_")


@pytest.mark.asyncio
async def test_no_trade_when_strategy_filters_out():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.get_orderbook = AsyncMock(
        return_value=_make_book(bids=[], asks=[])
    )

    path = AutonomousExecutionPath(
        live_data=live_data,
        strategies=[],
    )
    result = await path.run_cycle("MARKET", "MARKET-YES")
    assert result["status"] == "no_trade"
    assert "No strategy emitted" in result["reason"]


@pytest.mark.asyncio
async def test_risk_cap_blocks_oversized_order():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())

    firewall = AsyncMock()
    firewall.evaluate = AsyncMock(return_value=FirewallVerdict(allow=True, reason="mock"))
    firewall.submit = AsyncMock(return_value=LiveOrderResult(success=True, order_id="x", proof_reference="pref"))

    caps = _caps_with_market()
    caps.max_single_order_cents = 10  # order value is 52c
    with patch("core.config_loader.load_caps", return_value=caps):
        path = AutonomousExecutionPath(
            live_data=live_data,
            firewall=firewall,
        )
        result = await path.run_cycle(
            "MARKET",
            "MARKET-YES",
            strategy_name="OrderbookSpreadCaptureStrategy",
        )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "risk"
    assert "cap" in result["reason"].lower()
    firewall.submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_compliance_blocks_blocked_category():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())

    firewall = AsyncMock()
    firewall.evaluate = AsyncMock(return_value=FirewallVerdict(allow=True, reason="mock"))
    firewall.submit = AsyncMock(return_value=LiveOrderResult(success=True, order_id="x", proof_reference="pref"))

    caps = _caps_with_market()
    caps.blocked_categories = ["MARKET"]
    with patch("core.config_loader.load_caps", return_value=caps):
        path = AutonomousExecutionPath(
            live_data=live_data,
            firewall=firewall,
        )
        result = await path.run_cycle(
            "MARKET",
            "MARKET-YES",
            strategy_name="OrderbookSpreadCaptureStrategy",
        )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "compliance"
    firewall.submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_kill_switch_blocks_before_submit():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.enable_kill_switch("test")

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())

    firewall = AsyncMock()
    firewall.evaluate = AsyncMock(
        return_value=FirewallVerdict(allow=False, reason="Kill switch active", rejected_by="kill_switch")
    )
    firewall.submit = AsyncMock()

    path = AutonomousExecutionPath(live_data=live_data, firewall=firewall)
    result = await path.run_cycle(
        "MARKET",
        "MARKET-YES",
        strategy_name="OrderbookSpreadCaptureStrategy",
    )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "kill_switch"
    firewall.submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_orderbook_fetch_failure_is_blocked():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(side_effect=RuntimeError("no creds"))

    path = AutonomousExecutionPath(live_data=live_data)
    result = await path.run_cycle("MARKET", "MARKET-YES")
    assert result["status"] == "blocked"
    assert result["rejected_by"] == "live_data"


@pytest.mark.asyncio
async def test_limit_orders_only_from_firewall():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    live_data = AsyncMock()
    live_data.client = AsyncMock()
    live_data.get_orderbook = AsyncMock(return_value=_make_book())
    live_data.get_resting_orders = AsyncMock(return_value={"orders": []})
    live_data.get_fills = AsyncMock(return_value={"fills": []})

    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "ord-123"}}
    exposure = ExposureTracker()
    firewall = LiveBrokerFirewall(client, exposure)

    caps = _caps_with_market()
    with patch("core.config_loader.load_caps", return_value=caps), patch(
        "live_firewall.firewall.load_caps", return_value=caps
    ), patch.object(
        LiveBrokerFirewall, "_live_submit_enabled", return_value=True
    ):
        path = AutonomousExecutionPath(
            live_data=live_data,
            firewall=firewall,
            exposure_tracker=exposure,
        )
        await path.run_cycle(
            "MARKET",
            "MARKET-YES",
            strategy_name="OrderbookSpreadCaptureStrategy",
        )

    order = client.create_order.call_args[0][0]
    assert order["type"] == "limit"
    assert order.get("action") == "buy"


def test_firewall_order_path_report_generated():
    path = generate_firewall_order_path_report()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["static_analysis"]["autonomous_path_clean"] is True
    assert data["assertions"]["only_allowed_callers_invoke_create_order"] is True
    assert "LiveBrokerFirewall.submit" in data["runtime_proof"]["live_order_chokepoint"]


def test_autonomous_live_capped_path_report_generated():
    path = generate_autonomous_live_capped_path_report()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["mode_gating"]["required_mode"] == AccountMode.AUTONOMOUS_LIVE_CAPPED.value
    assert data["cap_respect"]["caps_source"] == "configs/caps.json"
    assert data["cap_respect"]["caps_read_only"] is True
    assert data["cap_respect"]["limit_orders_only"] is True
    assert any(
        step["component"] == "proof.ledger.write_proof"
        for step in data["chain"]
    )


def test_autonomous_path_source_has_no_create_order_call():
    source = Path("C:/src/engine/dummy/execution/autonomous_path.py").read_text(encoding="utf-8")
    assert _source_has_create_order_call(source) is False
