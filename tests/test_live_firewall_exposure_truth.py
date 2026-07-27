"""Adversarial truth tests for Dummy's single real-order chokepoint."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.ontology import CapConfig, FirewallVerdict
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall
from tests.test_autonomy_live_firewall_integration import _book, _forecast, _request


ALLOW = FirewallVerdict(allow=True, reason="test gate passed")


def _pass_non_metadata_gates(monkeypatch, firewall: LiveBrokerFirewall) -> None:
    monkeypatch.setattr(
        "live_firewall.firewall.load_caps",
        lambda: CapConfig(allowed_markets=["MARKET"]),
    )
    monkeypatch.setattr(
        firewall,
        "evaluate",
        AsyncMock(return_value=ALLOW),
    )
    monkeypatch.setattr(
        firewall,
        "_autonomy_risk_verdict",
        lambda request, required=False: ALLOW,
    )
    monkeypatch.setattr(
        firewall,
        "_net_ev_verdict",
        lambda request, forecast, caps: ALLOW,
    )
    monkeypatch.setattr(
        firewall,
        "_model_influence_verdict",
        lambda request, forecast: ALLOW,
    )
    monkeypatch.setattr(
        firewall,
        "_canary_readiness_verdict",
        lambda required=False: ALLOW,
    )
    monkeypatch.setattr(firewall, "live_authority_verdict", lambda: ALLOW)
    firewall.client.get_orderbook.return_value = _book()


def test_firewall_source_has_only_one_broker_submit_surface() -> None:
    source = Path("live_firewall/firewall.py").read_text(encoding="utf-8")
    assert "KalshiLiveBrokerFirewallAdapter" not in source
    assert "caps_confirmed=True" not in source
    assert "command_seal_ready=True" not in source
    assert "resolver_armable=True" not in source
    assert source.count("await self.client.create_order(") == 1
    assert "LEGACY_ADAPTER_SUBMIT_RETIRED_USE_CENTRAL_FIREWALL" in source


@pytest.mark.asyncio
async def test_accepted_order_is_reserved_but_not_a_position(monkeypatch) -> None:
    exposure = ExposureTracker()
    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "broker-1"}}
    firewall = LiveBrokerFirewall(client, exposure)
    _pass_non_metadata_gates(monkeypatch, firewall)
    monkeypatch.setattr(
        firewall,
        "_verified_live_compliance_verdict",
        AsyncMock(return_value=ALLOW),
    )

    result = await firewall.submit(_request(), _book(), _forecast())

    assert result.success is True
    assert result.broker_contacted is True
    assert result.order_id == "broker-1"
    assert exposure.positions == {}
    assert exposure.open_order_count() == 1
    assert exposure.open_orders[0]["state"] == "open"
    assert exposure.open_orders[0]["remaining_size"] == 1
    assert exposure.total_exposure_cents() == 52
    assert len(exposure.order_history) == 1
    client.create_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_transport_keeps_full_conservative_reservation(monkeypatch) -> None:
    exposure = ExposureTracker()
    client = AsyncMock()
    client.create_order.side_effect = TimeoutError("outcome unknown")
    firewall = LiveBrokerFirewall(client, exposure)
    _pass_non_metadata_gates(monkeypatch, firewall)
    monkeypatch.setattr(
        firewall,
        "_verified_live_compliance_verdict",
        AsyncMock(return_value=ALLOW),
    )

    result = await firewall.submit(_request(), _book(), _forecast())

    assert result.success is False
    assert result.broker_contacted is True
    assert result.error == "AMBIGUOUS_BROKER_OUTCOME:TimeoutError"
    assert exposure.positions == {}
    assert exposure.open_order_count() == 1
    assert exposure.open_orders[0]["state"] == "submit_outcome_unknown"
    assert exposure.total_exposure_cents() == 52


def test_partial_fills_are_cumulative_and_reserve_the_remainder() -> None:
    exposure = ExposureTracker()
    exposure.add_open_order(
        "broker-1",
        "MARKET",
        4,
        60,
        contract_ticker="MARKET",
        side="yes",
    )
    assert exposure.positions == {}
    assert exposure.total_exposure_cents() == 247

    assert exposure.record_cumulative_fill("broker-1", 1, 50) is True
    position = exposure.positions[("MARKET", "yes")]
    assert position.quantity == 1
    assert position.avg_price_cents == 50
    assert exposure.open_orders[0]["remaining_size"] == 3
    assert exposure.total_exposure_cents() == 50 + 3 * 60 + 7

    assert exposure.record_cumulative_fill("broker-1", 3, 54) is True
    position = exposure.positions[("MARKET", "yes")]
    assert position.quantity == 3
    assert position.avg_price_cents == 54
    assert exposure.open_orders[0]["remaining_size"] == 1
    assert exposure.total_exposure_cents() == 3 * 54 + 60 + 7

    # Replaying the same cumulative witness cannot double count the fill.
    assert exposure.record_cumulative_fill("broker-1", 3, 54) is True
    assert exposure.positions[("MARKET", "yes")].quantity == 3
    assert exposure.total_exposure_cents() == 3 * 54 + 60 + 7

    # A witnessed cancel releases only the unfilled remainder.
    assert exposure.record_cumulative_fill(
        "broker-1", 3, 54, terminal_state="canceled"
    ) is True
    assert exposure.open_order_count() == 0
    assert exposure.total_exposure_cents() == 3 * 54


def test_stale_reservation_survives_persistence_reload(tmp_path) -> None:
    state_path = tmp_path / "exposure.json"
    first = ExposureTracker(persist=True, state_path=state_path)
    empty_head = first.anchor_head()
    assert empty_head[0] == 0
    assert first.reserve_order_submission(
        "client-1",
        "MARKET",
        2,
        49,
        contract_ticker="MARKET",
        side="yes",
    ) is True
    reserved_head = first.anchor_head()
    assert reserved_head[0] == 1
    assert reserved_head[1] != empty_head[1]

    reloaded = ExposureTracker(persist=True, state_path=state_path)

    assert reloaded.state_healthy is True
    assert reloaded.anchor_head() == reserved_head
    assert reloaded.open_order_count() == 1
    assert reloaded.open_orders[0]["state"] == "submitting"
    assert reloaded.total_exposure_cents() == 102


def test_exposure_anchor_exposes_byte_rollback_as_revision_regression(
    tmp_path,
) -> None:
    state_path = tmp_path / "exposure.json"
    tracker = ExposureTracker(persist=True, state_path=state_path)
    assert tracker.reserve_order_submission(
        "client-1",
        "MARKET",
        1,
        49,
        contract_ticker="MARKET",
        side="yes",
    )
    earlier_bytes = state_path.read_bytes()
    earlier_head = tracker.anchor_head()
    assert tracker.confirm_open_order("client-1", "broker-1")
    later_head = tracker.anchor_head()
    assert later_head[0] > earlier_head[0]
    assert later_head[1] != earlier_head[1]

    state_path.write_bytes(earlier_bytes)
    rolled_back = ExposureTracker(persist=True, state_path=state_path)
    assert rolled_back.state_healthy is True
    assert rolled_back.anchor_head() == earlier_head


def test_terminal_reconciliation_is_idempotent_after_restart(tmp_path) -> None:
    state_path = tmp_path / "exposure.json"
    first = ExposureTracker(persist=True, state_path=state_path)
    assert first.reserve_order_submission(
        "proposal-1",
        "MARKET",
        1,
        50,
        contract_ticker="MARKET",
        side="yes",
    ) is True
    assert first.confirm_open_order("proposal-1", "broker-1") is True
    reconciliation_id = "a" * 64
    assert first.record_cumulative_fill(
        "proposal-1",
        1,
        50,
        terminal_state="filled",
        reconciliation_id=reconciliation_id,
    ) is True

    reloaded = ExposureTracker(persist=True, state_path=state_path)
    assert reloaded.record_cumulative_fill(
        "proposal-1",
        1,
        50,
        terminal_state="filled",
        reconciliation_id=reconciliation_id,
    ) is True
    assert reloaded.state_healthy is True
    assert reloaded.open_order_count() == 0
    assert reloaded.positions[("MARKET", "yes")].quantity == 1

    settlement_id = "b" * 64
    assert reloaded.record_position_close(
        "MARKET",
        "yes",
        reconciliation_id=settlement_id,
    ) is True
    settled = ExposureTracker(persist=True, state_path=state_path)
    assert settled.record_position_close(
        "MARKET",
        "yes",
        reconciliation_id=settlement_id,
    ) is True
    assert settled.state_healthy is True
    assert settled.positions == {}


@pytest.mark.asyncio
async def test_verified_metadata_is_required_before_broker_contact(monkeypatch) -> None:
    client = AsyncMock()
    client.get_market.side_effect = RuntimeError("metadata unavailable")
    firewall = LiveBrokerFirewall(client, ExposureTracker())
    _pass_non_metadata_gates(monkeypatch, firewall)

    result = await firewall.submit(_request(), _book(), _forecast())

    assert result.success is False
    assert result.broker_contacted is False
    assert result.error == "Verified Kalshi compliance metadata unavailable"
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_metadata_governs_category_without_ticker_inference(
    monkeypatch,
) -> None:
    client = AsyncMock()
    client.get_market.return_value = {
        "market": {
            "ticker": "POLITICS-LOOKING-SPORT",
            "event_ticker": "EVT",
            "status": "open",
            "close_time": (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat(),
        }
    }
    client.get_event.return_value = {
        "event": {
            "event_ticker": "EVT",
            "series_ticker": "SERIES",
            "category": "Sports",
        }
    }
    client.get_series.return_value = {
        "series": {
            "ticker": "SERIES",
            "category": "Sports",
            "tags": ["Basketball"],
        }
    }
    caps = CapConfig(blocked_categories=["category:Politics"])
    monkeypatch.setattr("live_firewall.firewall.load_caps", lambda: caps)
    firewall = LiveBrokerFirewall(client, ExposureTracker())

    verdict = await firewall._verified_live_compliance_verdict(
        _request(
            market_ticker="POLITICS-LOOKING-SPORT",
            contract_ticker="POLITICS-LOOKING-SPORT",
        )
    )

    assert verdict.allow is True
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_retired_adapter_shim_never_contacts_broker() -> None:
    client = AsyncMock()
    firewall = LiveBrokerFirewall(client, ExposureTracker())

    result = await firewall.submit_limit_order_adapter(
        SimpleNamespace(proof_id="legacy-proof")
    )

    assert result.success is False
    assert result.broker_contacted is False
    assert result.error == "LEGACY_ADAPTER_SUBMIT_RETIRED_USE_CENTRAL_FIREWALL"
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_sink_owned_book_blocks_stale_caller_depth_change(monkeypatch) -> None:
    exposure = ExposureTracker()
    client = AsyncMock()
    # Caller saw a passive 50c bid against a 52c ask. At the final sink read,
    # the ask moved to 50c, so submitting it would silently become taker flow.
    client.get_orderbook.return_value = _book().model_copy(
        update={
            "asks": [_book().asks[0].model_copy(update={"price": 50})],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    firewall = LiveBrokerFirewall(client, exposure)
    _pass_non_metadata_gates(monkeypatch, firewall)
    client.get_orderbook.return_value = _book().model_copy(
        update={
            "asks": [_book().asks[0].model_copy(update={"price": 50})],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    monkeypatch.setattr(
        firewall,
        "_verified_live_compliance_verdict",
        AsyncMock(return_value=ALLOW),
    )
    evaluations = 0

    async def evaluate_with_final_depth(request, book, forecast):
        nonlocal evaluations
        evaluations += 1
        if evaluations == 1:
            return ALLOW
        return FirewallVerdict(
            allow=False,
            reason="Passive maker limit became marketable on fresh depth",
            rejected_by="execution_role",
        )

    monkeypatch.setattr(firewall, "evaluate", evaluate_with_final_depth)

    result = await firewall.submit(_request(), _book(), _forecast())

    assert result.success is False
    assert result.broker_contacted is False
    assert "marketable" in (result.error or "").lower()
    assert exposure.open_order_count() == 0
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_sink_owned_taker_book_requires_full_side_depth(monkeypatch) -> None:
    exposure = ExposureTracker()
    client = AsyncMock()
    thin_book = _book().model_copy(
        update={
            "asks": [_book().asks[0].model_copy(update={"size": 1})],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    client.get_orderbook.return_value = thin_book
    firewall = LiveBrokerFirewall(client, exposure)
    _pass_non_metadata_gates(monkeypatch, firewall)
    client.get_orderbook.return_value = thin_book
    monkeypatch.setattr(
        firewall,
        "_verified_live_compliance_verdict",
        AsyncMock(return_value=ALLOW),
    )
    evaluations = 0

    async def evaluate_with_final_depth(request, book, forecast):
        nonlocal evaluations
        evaluations += 1
        if evaluations == 1:
            return ALLOW
        return FirewallVerdict(
            allow=False,
            reason="Fresh side-specific depth cannot execute the taker request",
            rejected_by="executable_depth",
        )

    monkeypatch.setattr(firewall, "evaluate", evaluate_with_final_depth)
    request = _request(
        price_cents=52,
        size=2,
        liquidity_role="taker",
    )
    caller_book = _book().model_copy(
        update={"asks": [_book().asks[0].model_copy(update={"size": 10})]}
    )

    result = await firewall.submit(request, caller_book, _forecast())

    assert result.success is False
    assert result.broker_contacted is False
    assert "depth" in (result.error or "").lower()
    assert exposure.open_order_count() == 0
    client.create_order.assert_not_awaited()
