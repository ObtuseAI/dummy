"""No-bypass proofs for the autonomous central live-firewall boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.ontology import (
    FirewallVerdict,
    Forecast,
    LiveOrderRequest,
    OrderBook,
    OrderBookLevel,
)
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall


def _request(**overrides) -> LiveOrderRequest:
    values = {
        "proposal_id": "autonomy-test",
        "market_ticker": "MARKET",
        "contract_ticker": "MARKET",
        "side": "yes",
        "price_cents": 50,
        "size": 1,
        "strategy_proof_reference": "strategy:test",
        "forecast_proof_reference": "forecast:test",
        "adapter_name": "kalshi_live_firewall_adapter",
        "expiration_ts": int(datetime.now(timezone.utc).timestamp()) + 60,
    }
    values.update(overrides)
    return LiveOrderRequest(**values)


def _book() -> OrderBook:
    return OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET",
        bids=[OrderBookLevel(price=48, size=20)],
        asks=[OrderBookLevel(price=52, size=20)],
        timestamp=datetime.now(timezone.utc),
    )


def _forecast() -> Forecast:
    now = datetime.now(timezone.utc)
    return Forecast(
        market_ticker="MARKET",
        contract_ticker="MARKET",
        event_title="Event",
        contract_title="Contract",
        market_implied_probability=Decimal("0.50"),
        dummy_probability=Decimal("0.60"),
        probability_delta=Decimal("0.10"),
        confidence_score=Decimal("0.80"),
        uncertainty_band=(Decimal("0.55"), Decimal("0.65")),
        expected_edge=Decimal("0.10"),
        edge_after_fees=Decimal("0.08"),
        freshness_score=Decimal("1"),
        liquidity_score=Decimal("1"),
        spread_score=Decimal("1"),
        orderbook_depth_score=Decimal("1"),
        settlement_risk_score=Decimal("0.2"),
        source_summary="test",
        model_summary="test",
        calibration_notes="test",
        timestamp=now,
        expiration=now + timedelta(hours=1),
        strategy_references=["strategy:test"],
        proof_reference="forecast:test",
    )


def test_executor_source_has_no_direct_adapter_bypass():
    source = Path("autonomy/executor.py").read_text(encoding="utf-8")
    assert "KalshiLiveBrokerFirewallAdapter" not in source
    assert "submit_limit_order(" not in source
    assert "adapter_factory" not in source
    assert "caps_confirmed=True" not in source
    assert "command_seal_ready=True" not in source
    assert "resolver_armable=True" not in source
    assert "firewall.submit(request, orderbook, firewall_forecast)" in source


def test_legacy_proof_runners_cannot_exercise_retired_submit_surface():
    for path in (
        Path("core/second_proof_runner.py"),
        Path("predator_mesh/v298/reports.py"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "submit_limit_order_adapter(" not in source


def test_live_submit_config_remains_disabled():
    assert json.loads(Path("configs/live_submit.json").read_text(encoding="utf-8")) == {
        "enabled": False
    }


@pytest.mark.parametrize("missing_gate", ["risk", "authority"])
def test_direct_submit_cannot_skip_any_live_safety_gate(monkeypatch, missing_gate):
    client = AsyncMock()
    client.create_order.return_value = {"order": {"order_id": "must-not-exist"}}
    firewall = LiveBrokerFirewall(client, ExposureTracker())
    monkeypatch.setattr(
        firewall,
        "evaluate",
        AsyncMock(return_value=FirewallVerdict(allow=True, reason="domain gates passed")),
    )

    allow = FirewallVerdict(allow=True, reason="test pass")
    blocked = FirewallVerdict(
        allow=False,
        reason=f"{missing_gate}_blocked",
        rejected_by=missing_gate,
    )
    monkeypatch.setattr(
        firewall,
        "_autonomy_risk_verdict",
        lambda request, required=False: blocked if missing_gate == "risk" else allow,
    )
    monkeypatch.setattr(
        firewall,
        "live_authority_verdict",
        lambda: blocked if missing_gate == "authority" else allow,
    )

    result = asyncio.run(firewall.submit(_request(), _book(), _forecast()))

    assert result.success is False
    assert result.error == f"{missing_gate}_blocked"
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()


@pytest.mark.parametrize("historical_ready", [False, True])
def test_paper_result_cannot_enable_or_block_submit_authority(
    monkeypatch,
    historical_ready,
):
    """Neither sign of the retired paper result is consulted at the sink."""
    client = AsyncMock()
    firewall = LiveBrokerFirewall(client, ExposureTracker())
    allow = FirewallVerdict(allow=True, reason="live authority")
    monkeypatch.setattr(
        firewall,
        "evaluate",
        AsyncMock(return_value=FirewallVerdict(allow=True, reason="domain gates passed")),
    )
    monkeypatch.setattr(
        firewall,
        "_autonomy_risk_verdict",
        lambda request, required=False: allow,
    )
    monkeypatch.setattr(
        firewall,
        "live_authority_verdict",
        lambda: FirewallVerdict(
            allow=False,
            reason="live_submit_disabled",
            rejected_by="live_submit",
        ),
    )

    def retired_gate_must_not_run(*_args, **_kwargs):
        raise AssertionError(
            f"retired paper result was consulted: {historical_ready}"
        )

    monkeypatch.setattr(
        firewall,
        "_canary_readiness_verdict",
        retired_gate_must_not_run,
    )
    result = asyncio.run(firewall.submit(_request(), _book(), _forecast()))

    assert result.success is False
    assert result.error == "live_submit_disabled"
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()


def test_old_live_enabled_boolean_cannot_bypass_actual_authority(tmp_path, monkeypatch):
    live_submit = tmp_path / "live_submit.json"
    live_submit.write_text('{"enabled": false}', encoding="utf-8")
    monkeypatch.setattr("live_firewall.firewall.LIVE_SUBMIT_PATH", live_submit)

    client = AsyncMock()
    firewall = LiveBrokerFirewall(client, ExposureTracker())
    monkeypatch.setattr(
        firewall,
        "evaluate",
        AsyncMock(return_value=FirewallVerdict(allow=True, reason="domain gates passed")),
    )
    monkeypatch.setattr(
        firewall,
        "_autonomy_risk_verdict",
        lambda request, required=False: FirewallVerdict(allow=True, reason="risk"),
    )
    monkeypatch.setattr(
        firewall,
        "_canary_readiness_verdict",
        lambda required=False: FirewallVerdict(allow=True, reason="canary"),
    )
    monkeypatch.setattr(firewall, "_live_submit_enabled", lambda: True)

    result = asyncio.run(firewall.submit(_request(), _book(), _forecast()))

    assert result.success is False
    assert result.error == "live_submit_disabled"
    client.create_order.assert_not_awaited()


def test_risk_attestation_detects_file_change(tmp_path):
    risk_path = tmp_path / "risk.json"
    payload = {
        "accounting_version": 2,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "stage": 1,
        "bankroll_cents": 100_000,
        "open_exposure_cents": 0,
        "open_markets": 0,
        "hard_stopped": False,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    risk_path.write_bytes(encoded)
    request = _request(
        risk_state_sha256=hashlib.sha256(encoded).hexdigest(),
        risk_snapshot={
            "stage": 1,
            "bankroll_cents": 100_000,
            "open_exposure_cents": 0,
            "open_markets": 0,
        },
    )
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        autonomy_risk_state_path=risk_path,
        require_autonomy_risk_state=True,
    )
    assert firewall._autonomy_risk_verdict(request).allow is True

    payload["open_exposure_cents"] = 50
    risk_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    verdict = firewall._autonomy_risk_verdict(request)
    assert verdict.allow is False
    assert verdict.rejected_by == "autonomy_risk_state"
