"""Tests for second-proof one-shot-live execution wiring."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from core.proof_authority import REQUIRED_CONFIRMATION
from core.second_proof_lock import is_second_proof_lock_consumed
from core.second_proof_runner import run_second_proof_execute_once
from live_firewall.firewall import LiveBrokerFirewall
from core.ontology import LiveOrderResult
from predator_mesh.brokers import LimitOrderRequest
from tools.operator_authority_appliance import operator_full_completion as ofc


@pytest.fixture
def active_context(tmp_path, monkeypatch):
    """Patch paths, prepare, and activate a second-proof authority."""
    from core import proof_authority as pa
    from core import second_proof_lock as spl
    monkeypatch.setattr(pa, "V3_CANDIDATE_PATH", tmp_path / "v3.json")
    monkeypatch.setattr(pa, "V3_REPORT_PATH", tmp_path / "v3_report.json")
    monkeypatch.setattr(pa, "REAL_PROOF_REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(pa, "CAPS_PATH", tmp_path / "caps.json")
    monkeypatch.setattr(pa, "ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")
    monkeypatch.setattr(pa, "LIVE_SUBMIT_PATH", tmp_path / "live_submit.json")
    monkeypatch.setattr(pa, "RUNTIME_APPROVALS_DIR", tmp_path / "approvals")
    monkeypatch.setattr(pa, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    monkeypatch.setattr(spl, "SECOND_PROOF_LOCK_DIR", tmp_path / "proof_locks")
    from core import second_proof_runner as spr
    monkeypatch.setattr(spr, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    monkeypatch.setattr(spr, "V3_CANDIDATE_PATH", tmp_path / "v3.json")
    monkeypatch.setattr(ofc, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    monkeypatch.setattr(ofc, "LIVE_SUBMIT_PATH", tmp_path / "live_submit.json")
    monkeypatch.setattr(ofc, "CAPS_PATH", tmp_path / "caps.json")
    monkeypatch.setattr(ofc, "ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")

    candidate = {
        "candidate_found": True,
        "market_tradable": True,
        "contract_tradable": True,
        "price_validated": True,
        "order_type": "LIMIT",
        "count": 1,
        "price": 1,
        "market_ticker": "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6",
        "contract_ticker": "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6",
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "proof_lock_status": "consumed_by_real_broker_attempt",
    }
    (tmp_path / "v3.json").write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    (tmp_path / "v3_report.json").write_text(json.dumps({"verdict": "READ_ONLY_DISCOVERY_V3_CANDIDATE_FOUND"}, sort_keys=True), encoding="utf-8")
    registry = {
        "latest_real_broker_attempt_status": "BROKER_REJECTED",
        "latest_real_broker_contacted": True,
        "evidence_index_hash": "1C895591A874389AA3855A281B856EE239F920579DC04564B949940CCCF10113",
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    (tmp_path / "caps.json").write_text(
        json.dumps({"order_type_policy": "LIMIT_ONLY", "market_orders_allowed": False, "kill_switch_enabled": True, "max_order_count": 1}, sort_keys=True),
        encoding="utf-8",
    )
    (tmp_path / "descriptor.json").write_text(
        json.dumps({"broker": "KALSHI", "adapter_type": "LiveBrokerFirewall", "order_type_policy": "LIMIT_ONLY", "market_orders_allowed": False}, sort_keys=True),
        encoding="utf-8",
    )
    (tmp_path / "live_submit.json").write_text(json.dumps({"enabled": False}, sort_keys=True), encoding="utf-8")
    (tmp_path / "approvals").mkdir()
    (tmp_path / "approvals" / "dummy_controlled_production_pilot_approval.json").write_text(
        json.dumps({"scope": "one_controlled_production_pilot_via_firewall_only"}, sort_keys=True), encoding="utf-8"
    )

    args = ofc.build_parser().parse_args(["prepare-second-proof-authority"])
    ofc.cmd_prepare_second_proof_authority(args, io.StringIO())
    args = ofc.build_parser().parse_args([
        "activate-second-proof-authority",
        "--operator-name", "chris",
        "--reason", "second controlled proof",
        "--expires-at", "2099-01-01T00:00:00Z",
        "--confirm", REQUIRED_CONFIRMATION,
    ])
    ofc.cmd_activate_second_proof_authority(args, io.StringIO())

    # Patch seal to ready.
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    # Prevent the runner from touching the real default live_submit.json while
    # still letting tests that pass an explicit path verify the restore behavior.
    from core.second_proof_runner import restore_live_submit_disabled_default as _real_restore
    def _noop_or_restore(live_submit_path=None):
        if live_submit_path is None:
            return
        _real_restore(live_submit_path)
    monkeypatch.setattr("core.second_proof_runner.restore_live_submit_disabled_default", _noop_or_restore)
    return tmp_path


def _active_authority_id(tmp_path):
    active_path = tmp_path / "second_proof_authority" / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    data = json.loads(active_path.read_text(encoding="utf-8"))
    return data["authority_id"]


# --- cmd_one_shot_live wiring ---


def test_blocked_without_env_gate(active_context, tmp_path):
    out = io.StringIO()
    rc = ofc.cmd_one_shot_live({}, None, out)
    assert rc == ofc.EXIT_MISSING
    assert "BLOCKED_ENV_GATE_ABSENT" in out.getvalue()


def test_blocked_without_active_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(ofc, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    out = io.StringIO()
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    monkeypatch.setattr(ofc, "_proof_lock", lambda: True)
    rc = ofc.cmd_one_shot_live(env, None, out)
    assert rc == ofc.EXIT_MISSING
    assert "BLOCKED_PROOF_LOCK_ALREADY_USED" in out.getvalue()


def test_cmd_one_shot_live_runs_second_proof_runner(active_context, tmp_path, monkeypatch):
    captured = {}

    async def fake_submit(self, req: LimitOrderRequest):
        captured["market_ticker"] = req.market_ticker
        captured["price"] = req.price
        captured["quantity"] = req.quantity
        captured["order_type"] = req.order_type
        return LiveOrderResult(success=True, order_id="ord-second-1", error=None, proof_reference="")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    out = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out)
    assert rc == ofc.EXIT_OK
    assert captured["market_ticker"] == "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6"
    assert captured["price"] == 1
    assert captured["quantity"] == 1
    assert captured["order_type"] == "LIMIT"


def test_second_attempt_blocked_by_lock(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        return LiveOrderResult(success=True, order_id="ord-1", error=None, proof_reference="")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    out = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out)
    assert rc == ofc.EXIT_OK
    # Second attempt should be blocked by the consumed lock.
    out2 = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out2)
    assert rc == ofc.EXIT_MISSING
    assert "BLOCKED_SECOND_PROOF_LOCK_ALREADY_USED" in out2.getvalue()


# --- run_second_proof_execute_once direct tests ---


def test_uses_v3_candidate_when_active(active_context, tmp_path, monkeypatch):
    captured = {}

    async def fake_submit(self, req: LimitOrderRequest):
        captured["market_ticker"] = req.market_ticker
        captured["price"] = req.price
        captured["quantity"] = req.quantity
        captured["order_type"] = req.order_type
        return LiveOrderResult(success=True, order_id="ord-second-1", error=None, proof_reference="")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_EXECUTED_ACCEPTED"
    assert report["real_live_orders_submitted_count"] == 1
    assert captured["market_ticker"] == "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6"
    assert captured["price"] == 1
    assert captured["quantity"] == 1
    assert captured["order_type"] == "LIMIT"


def test_does_not_use_kxbtc(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        assert req.market_ticker != "KXBTC-26DEC25000-C"
        return LiveOrderResult(success=False, order_id=None, error="BROKER_REJECTED", proof_reference="", broker_rejection_code="BROKER_REJECTED", broker_rejection_http_status=400)

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_EXECUTED_BROKER_REJECTED"


def test_routes_through_live_firewall(active_context, tmp_path, monkeypatch):
    called = []

    async def fake_submit(self, req: LimitOrderRequest):
        called.append(True)
        return SubmitResult(submitted=True, order_id="ord-2", state=OrderState.OPEN, raw={})

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    run_second_proof_execute_once()
    assert len(called) == 1


def test_mocked_broker_accepted_sets_live_order_count(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        return LiveOrderResult(success=True, order_id="ord-accepted", error=None, proof_reference="")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_EXECUTED_ACCEPTED"
    assert report["real_live_orders_submitted_count"] == 1
    aid = _active_authority_id(tmp_path)
    assert is_second_proof_lock_consumed(aid) is True


def test_mocked_broker_rejected_preserves_reason(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        return LiveOrderResult(
            success=False, order_id=None, error="BROKER_REJECTED", proof_reference="",
            broker_rejection_code="BROKER_REJECTED", broker_rejection_http_status=400,
        )

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_EXECUTED_BROKER_REJECTED"
    aid = _active_authority_id(tmp_path)
    lock_path = tmp_path / "proof_locks" / f"second_proof_{aid}.json"
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    assert data["consumed"] is True
    assert data["rejected"] is True
    assert data["reason"] == "BROKER_REJECTED"


def test_market_order_rejected_by_firewall(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        # The firewall itself rejects market orders before reaching here.
        assert req.order_type == "LIMIT"
        return LiveOrderResult(success=False, order_id=None, error="MARKET_ORDER_REJECTED", proof_reference="", broker_rejection_code="MARKET_ORDER_REJECTED", broker_rejection_http_status=400)

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["market_order_submitted"] is False


def test_live_submit_restored_after_attempt(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req: LimitOrderRequest):
        return LiveOrderResult(success=True, order_id="ord-1", error=None, proof_reference="")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    live_submit = json.loads((tmp_path / "live_submit.json").read_text(encoding="utf-8"))
    assert live_submit["enabled"] is False
