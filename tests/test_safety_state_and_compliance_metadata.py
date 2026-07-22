from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from compliance.governor import assess_compliance
from compliance.kalshi_metadata import (
    ComplianceMetadataError,
    SOURCE,
    fetch_verified_kalshi_compliance_metadata,
)
from core.config_loader import load_caps
from core.ontology import CapConfig, FirewallVerdict, LiveOrderRequest, MarketComplianceMetadata
from core.state import STATE, DummyState, RISK_STATE_SCHEMA_VERSION
from kalshi.client import KalshiClient
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall


def _metadata(
    *,
    market_ticker: str = "KXOPAQUE-26JUL22-A",
    category: str = "Sports",
    event_category: str | None = None,
    tags: list[str] | None = None,
    verified: bool = True,
) -> MarketComplianceMetadata:
    return MarketComplianceMetadata(
        source=SOURCE,
        received_at=datetime.now(timezone.utc),
        market_ticker=market_ticker,
        event_ticker="KXOPAQUE-26JUL22",
        series_ticker="KXOPAQUE",
        series_category=category,
        event_category=event_category if event_category is not None else category,
        series_tags=tags or [],
        verified=verified,
    )


def test_pytest_patches_canonical_and_direct_state_aliases_to_tmp(
    _isolated_runtime_risk_state,
    tmp_path,
):
    from autonomy.executor import Executor
    from autonomy.ontology import SessionMode
    from autonomy.risk_brain import RiskBrain
    from core import state as state_module

    assert STATE is _isolated_runtime_risk_state
    assert state_module.STATE is _isolated_runtime_risk_state
    assert _isolated_runtime_risk_state._state_path.is_relative_to(tmp_path)
    tracker = ExposureTracker()
    assert tracker.state_path == tmp_path / "runtime" / "live_exposure_state.json"
    assert RiskBrain().state_path == tmp_path / "runtime" / "autonomy_risk_state.json"
    assert Executor(SessionMode.SHADOW).risk_state_path == (
        tmp_path / "runtime" / "autonomy_risk_state_live.json"
    )
    assert LiveBrokerFirewall(None, tracker).autonomy_risk_state_path == (
        tmp_path / "runtime" / "autonomy_risk_state_live.json"
    )


def test_kill_switch_survives_restart_and_explicit_disable(tmp_path):
    path = tmp_path / "risk_state.json"
    state = DummyState(persist=True, state_path=path)

    assert state.enable_kill_switch("operator test") is True
    restarted = DummyState(persist=True, state_path=path)
    assert restarted.kill_switch.active is True
    assert restarted.kill_switch.reason == "operator test"
    assert restarted.kill_switch.triggered_at is not None

    assert restarted.disable_kill_switch() is True
    assert DummyState(persist=True, state_path=path).kill_switch.active is False


def test_emergency_stop_survives_restart(tmp_path):
    path = tmp_path / "risk_state.json"
    state = DummyState(persist=True, state_path=path)

    assert state.trigger_emergency_stop() is True
    restarted = DummyState(persist=True, state_path=path)

    assert restarted.emergency_stop.active is True
    assert restarted.emergency_stop.cancel_open_orders is True
    assert restarted.emergency_stop.triggered_at is not None

    assert restarted.clear_emergency_stop() is True
    assert DummyState(persist=True, state_path=path).emergency_stop.active is False


def test_legacy_state_migrates_with_both_controls_latched(tmp_path):
    path = tmp_path / "risk_state.json"
    path.write_text(
        json.dumps(
            {
                "utc_date": datetime.now(timezone.utc).date().isoformat(),
                "daily_loss_cents": 25,
                "processed_settlement_ids": ["settlement-1"],
            }
        ),
        encoding="utf-8",
    )

    state = DummyState(persist=True, state_path=path)
    migrated = json.loads(path.read_text(encoding="utf-8"))

    assert state.persistence_error is None
    assert state.kill_switch.active is True
    assert state.emergency_stop.active is True
    assert migrated["schema_version"] == RISK_STATE_SCHEMA_VERSION
    assert migrated["kill_switch"]["active"] is True
    assert migrated["emergency_stop"]["active"] is True
    assert migrated["daily_loss_cents"] == 25


@pytest.mark.parametrize(
    "bad_control",
    [
        {"kill_switch": {"active": "false"}, "emergency_stop": {"active": False}},
        {"kill_switch": {"active": False}, "emergency_stop": {"active": 0}},
        {"kill_switch": {"active": True}, "emergency_stop": {"active": False}},
    ],
)
def test_malformed_control_state_is_quarantined_and_cannot_be_disabled(tmp_path, bad_control):
    path = tmp_path / "risk_state.json"
    payload = {
        "schema_version": RISK_STATE_SCHEMA_VERSION,
        "utc_date": datetime.now(timezone.utc).date().isoformat(),
        "daily_loss_cents": 0,
        "processed_settlement_ids": [],
        **bad_control,
    }
    original = json.dumps(payload)
    path.write_text(original, encoding="utf-8")

    state = DummyState(persist=True, state_path=path)

    assert state.persistence_error is not None
    assert state.kill_switch.active is True
    assert state.emergency_stop.active is True
    assert state.disable_kill_switch() is False
    assert state.kill_switch.active is True
    assert path.read_text(encoding="utf-8") == original
    assert state.enable_kill_switch("still blocked") is False
    assert state.trigger_emergency_stop() is False
    assert state.clear_emergency_stop() is False
    assert state.record_realized_pnl(-10, settlement_id="unknown") is False
    assert path.read_text(encoding="utf-8") == original


def test_failed_kill_switch_deactivation_remains_latched(tmp_path, monkeypatch):
    path = tmp_path / "risk_state.json"
    state = DummyState(persist=True, state_path=path)
    assert state.enable_kill_switch("operator test") is True

    def fail_replace(_source, _destination):
        raise PermissionError("read only")

    monkeypatch.setattr("core.state.os.replace", fail_replace)
    assert state.disable_kill_switch() is False
    assert state.kill_switch.active is True

    # The last durable record was also active.
    durable = json.loads(path.read_text(encoding="utf-8"))
    assert durable["kill_switch"]["active"] is True


def test_refresh_observes_stop_latched_by_another_process(tmp_path):
    path = tmp_path / "risk_state.json"
    dashboard_state = DummyState(persist=True, state_path=path)
    assert dashboard_state.verify_persistence() is True
    executor_state = DummyState(persist=True, state_path=path)
    assert executor_state.kill_switch.active is False

    assert dashboard_state.enable_kill_switch("operator") is True
    assert executor_state.kill_switch.active is False
    assert executor_state.refresh_persisted_state() is True
    assert executor_state.kill_switch.active is True


def test_missing_state_on_live_refresh_fails_closed(tmp_path):
    state = DummyState(persist=True, state_path=tmp_path / "missing.json")

    assert state.refresh_persisted_state() is False
    assert state.kill_switch.active is True
    assert state.emergency_stop.active is True
    assert state.persistence_error is not None


def test_opaque_ticker_is_blocked_by_verified_kalshi_category():
    caps = CapConfig(blocked_categories=["Elections", "Politics"])

    verdict = assess_compliance(
        "KXOPAQUE-26JUL22-A",
        "KXOPAQUE-26JUL22-A",
        caps=caps,
        metadata=_metadata(category="Politics"),
        require_verified_metadata=True,
    )

    assert verdict.passed is False
    assert verdict.blocked_categories == ["Politics"]


def test_semantic_ticker_cannot_fake_a_blocked_category():
    caps = CapConfig(blocked_categories=["Politics"])
    ticker = "POLITICS-ELECTIONS-US-LOOKALIKE"

    verdict = assess_compliance(
        ticker,
        ticker,
        caps=caps,
        metadata=_metadata(market_ticker=ticker, category="Sports"),
        require_verified_metadata=True,
    )

    assert verdict.passed is True


def test_tag_selectors_are_exact_not_substring_matches():
    metadata = _metadata(category="Elections", tags=["US Elections"])

    blocked = assess_compliance(
        metadata.market_ticker,
        metadata.market_ticker,
        caps=CapConfig(blocked_categories=["tag:US Elections"]),
        metadata=metadata,
        require_verified_metadata=True,
    )
    safe = assess_compliance(
        metadata.market_ticker,
        metadata.market_ticker,
        caps=CapConfig(blocked_categories=["tag:US"]),
        metadata=metadata,
        require_verified_metadata=True,
    )

    assert blocked.passed is False
    assert safe.passed is True


@pytest.mark.parametrize(
    ("metadata", "reason_fragment"),
    [
        (None, "required"),
        ({"bad": "shape"}, "malformed"),
        (_metadata(market_ticker="OTHER"), "mismatch"),
        (_metadata(verified=False), "not verified"),
    ],
)
def test_required_compliance_metadata_fails_closed(metadata, reason_fragment):
    verdict = assess_compliance(
        "KXOPAQUE-26JUL22-A",
        "KXOPAQUE-26JUL22-A",
        caps=CapConfig(blocked_categories=["Politics"]),
        metadata=metadata,
        require_verified_metadata=True,
    )

    assert verdict.passed is False
    assert reason_fragment in verdict.reason.lower()


class _MetadataClient:
    def __init__(self, *, category: str = "Elections", tags: list[str] | None = None):
        self.category = category
        self.tags = ["US Elections"] if tags is None else tags
        self.calls: list[tuple[str, str]] = []
        self.create_order = AsyncMock()

    async def get_market(self, ticker):
        self.calls.append(("market", ticker))
        return {
            "market": {
                "ticker": ticker,
                "event_ticker": "EVENT-1",
                "status": "open",
                "close_time": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
            }
        }

    async def get_event(self, ticker):
        self.calls.append(("event", ticker))
        return {
            "event": {
                "event_ticker": ticker,
                "series_ticker": "SERIES-1",
                "category": self.category,
            }
        }

    async def get_series(self, ticker):
        self.calls.append(("series", ticker))
        return {
            "series": {
                "ticker": ticker,
                "category": self.category,
                "tags": self.tags,
            }
        }


@pytest.mark.asyncio
async def test_resolver_links_market_event_and_series_exactly():
    client = _MetadataClient()

    metadata = await fetch_verified_kalshi_compliance_metadata(client, "OPAQUE-MARKET")

    assert metadata.market_ticker == "OPAQUE-MARKET"
    assert metadata.event_ticker == "EVENT-1"
    assert metadata.series_ticker == "SERIES-1"
    assert metadata.series_category == "Elections"
    assert metadata.series_tags == ["US Elections"]
    assert metadata.verified is True
    assert client.calls == [
        ("market", "OPAQUE-MARKET"),
        ("event", "EVENT-1"),
        ("series", "SERIES-1"),
    ]


@pytest.mark.asyncio
async def test_resolver_rejects_cross_market_metadata_attachment():
    client = _MetadataClient()

    async def wrong_market(_ticker):
        return {"market": {"ticker": "DIFFERENT", "event_ticker": "EVENT-1"}}

    client.get_market = wrong_market
    with pytest.raises(ComplianceMetadataError, match="MARKET_TICKER_MISMATCH"):
        await fetch_verified_kalshi_compliance_metadata(client, "OPAQUE-MARKET")


@pytest.mark.asyncio
async def test_resolver_rejects_conflicting_event_and_series_categories():
    client = _MetadataClient()

    async def conflicting_series(ticker):
        return {"series": {"ticker": ticker, "category": "Sports", "tags": []}}

    client.get_series = conflicting_series
    with pytest.raises(ComplianceMetadataError, match="CATEGORY_MISMATCH"):
        await fetch_verified_kalshi_compliance_metadata(client, "OPAQUE-MARKET")


@pytest.mark.asyncio
async def test_kalshi_client_uses_read_only_event_and_series_endpoints():
    client = object.__new__(KalshiClient)
    client._request = AsyncMock(return_value={})

    await client.get_event("EVENT-1")
    await client.get_series("SERIES-1")

    assert client._request.await_args_list[0].args == ("GET", "/events/EVENT-1")
    assert client._request.await_args_list[1].args == ("GET", "/series/SERIES-1")


def _live_request(ticker: str) -> LiveOrderRequest:
    return LiveOrderRequest(
        proposal_id="proposal-compliance-test",
        market_ticker=ticker,
        contract_ticker=ticker,
        side="yes",
        price_cents=40,
        size=1,
        strategy_proof_reference="strategy-proof",
        forecast_proof_reference="forecast-proof",
        adapter_name="kalshi_live_firewall_adapter",
    )


@pytest.mark.asyncio
async def test_live_sink_blocks_opaque_ticker_from_verified_category_before_broker_contact():
    client = _MetadataClient(category="Politics", tags=["International"])
    firewall = LiveBrokerFirewall(client, ExposureTracker())
    firewall.evaluate = AsyncMock(
        return_value=FirewallVerdict(allow=True, reason="prior gates passed")
    )
    firewall._autonomy_risk_verdict = lambda _request, required: FirewallVerdict(
        allow=True, reason=f"risk required={required}"
    )
    firewall._canary_readiness_verdict = lambda required: FirewallVerdict(
        allow=True, reason=f"readiness required={required}"
    )
    firewall.live_authority_verdict = lambda: FirewallVerdict(
        allow=True, reason="authority passed"
    )

    result = await firewall.submit(
        _live_request("KXOPAQUE-26JUL22-A"),
        None,
        None,
    )

    assert result.success is False
    assert "Politics" in (result.error or "")
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_safe_category_beats_adversarial_semantic_ticker_text():
    ticker = "POLITICS-ELECTIONS-US-LOOKALIKE"
    client = _MetadataClient(category="Sports", tags=["Basketball"])
    firewall = LiveBrokerFirewall(client, ExposureTracker())

    verdict = await firewall._verified_live_compliance_verdict(_live_request(ticker))

    assert verdict.allow is True
    client.create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_equity_category_is_quarantined_at_live_sink():
    ticker = "KXOPAQUE-26JUL22-A"
    client = _MetadataClient(category="Financials", tags=["Single company"])
    firewall = LiveBrokerFirewall(client, ExposureTracker())

    verdict = await firewall._verified_live_compliance_verdict(
        _live_request(ticker)
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "prediction_target_quarantine"
    assert "zero prediction and execution authority" in verdict.reason
    client.create_order.assert_not_awaited()


def test_evaluate_contains_no_ticker_prefix_category_oracle():
    source = inspect.getsource(LiveBrokerFirewall.evaluate)

    assert "blocked_category" not in source
    assert "assess_compliance(" not in source


def test_shipped_blocked_categories_use_real_kalshi_category_values():
    assert load_caps().blocked_categories == ["Elections", "Politics"]
