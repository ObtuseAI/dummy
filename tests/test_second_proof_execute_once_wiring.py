"""Tests for second-proof one-shot-live execution wiring."""

from __future__ import annotations

from datetime import datetime, timezone

import io
import json

import pytest

from tests.caps_authority_test_helpers import install_registered_caps_authority
from core.proof_authority import REQUIRED_CONFIRMATION
from core.second_proof_lock import is_second_proof_lock_consumed
from core.second_proof_runner import run_second_proof_execute_once
from live_firewall.firewall import LiveBrokerFirewall
from tools.operator_authority_appliance import operator_full_completion as ofc


RETIRED_REASON = "LEGACY_SECOND_PROOF_RUNNER_RETIRED_USE_CENTRAL_FIREWALL"


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
        # A candidate's tradability claim expires (see
        # CANDIDATE_MAX_AGE_SECONDS). "Just validated" is this fixture's
        # intent, so stamp now rather than freezing a date that would rot.
        "created_at": datetime.now(timezone.utc).isoformat(),
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
    install_registered_caps_authority(
        monkeypatch, tmp_path / "caps.json", patch_operator_appliance=True
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


def test_cmd_one_shot_live_blocks_retired_second_proof_runner(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    out = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out)
    assert rc == ofc.EXIT_EXTERNAL
    assert RETIRED_REASON in out.getvalue()
    assert calls == []


def test_retired_runner_does_not_consume_lock(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    out = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out)
    assert rc == ofc.EXIT_EXTERNAL
    out2 = io.StringIO()
    rc = ofc.cmd_one_shot_live(env, None, out2)
    assert rc == ofc.EXIT_EXTERNAL
    assert RETIRED_REASON in out2.getvalue()
    assert calls == []
    assert is_second_proof_lock_consumed(_active_authority_id(tmp_path)) is False


# --- run_second_proof_execute_once direct tests ---


def test_active_v3_candidate_is_blocked_in_retired_runner(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["block_reason"] == RETIRED_REASON
    assert report["real_live_orders_submitted_count"] == 0
    assert report["real_broker_contacted"] is False
    assert calls == []


def test_does_not_use_kxbtc(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not submit any ticker")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["block_reason"] == RETIRED_REASON
    assert calls == []


def test_retired_runner_does_not_route_through_compatibility_adapter(active_context, tmp_path, monkeypatch):
    called = []

    async def fake_submit(self, req):
        called.append(True)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once()
    assert report["block_reason"] == RETIRED_REASON
    assert called == []


def test_mocked_retired_adapter_cannot_forge_acceptance(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["real_live_orders_submitted_count"] == 0
    assert calls == []
    aid = _active_authority_id(tmp_path)
    assert is_second_proof_lock_consumed(aid) is False


def test_mocked_retired_adapter_cannot_forge_broker_rejection(active_context, tmp_path, monkeypatch):
    calls = []

    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["block_reason"] == RETIRED_REASON
    assert calls == []
    aid = _active_authority_id(tmp_path)
    lock_path = tmp_path / "proof_locks" / f"second_proof_{aid}.json"
    assert is_second_proof_lock_consumed(aid) is False
    if lock_path.exists():
        assert json.loads(lock_path.read_text(encoding="utf-8"))["consumed"] is False


def test_market_order_rejected_by_firewall(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req):
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert report["market_order_submitted"] is False


def test_live_submit_restored_after_attempt(active_context, tmp_path, monkeypatch):
    async def fake_submit(self, req):
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", fake_submit)
    run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    live_submit = json.loads((tmp_path / "live_submit.json").read_text(encoding="utf-8"))
    assert live_submit["enabled"] is False
