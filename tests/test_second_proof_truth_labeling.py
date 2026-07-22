"""Truth-labeling tests for the retired second-proof compatibility runner."""

from __future__ import annotations

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


def _must_not_submit(calls):
    async def fake_submit(self, req):
        calls.append(req)
        raise AssertionError("retired runner must not call the compatibility submit adapter")

    return fake_submit


@pytest.fixture
def active_context(tmp_path, monkeypatch):
    """Same authority fixture shape as test_second_proof_execute_once_wiring."""
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
        "market_ticker": "KXTEST-TRUTH-LABELING",
        "contract_ticker": "KXTEST-TRUTH-LABELING",
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "proof_lock_status": "consumed_by_real_broker_attempt",
    }
    (tmp_path / "v3.json").write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    (tmp_path / "v3_report.json").write_text(json.dumps({"verdict": "OK"}, sort_keys=True), encoding="utf-8")
    registry = {
        "latest_real_broker_attempt_status": "BROKER_REJECTED",
        "latest_real_broker_contacted": True,
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
        "--reason", "truth labeling test",
        "--expires-at", "2099-01-01T00:00:00Z",
        "--confirm", REQUIRED_CONFIRMATION,
    ])
    ofc.cmd_activate_second_proof_authority(args, io.StringIO())
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    return tmp_path


def _authority_id(tmp_path):
    active = tmp_path / "second_proof_authority" / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    return json.loads(active.read_text(encoding="utf-8"))["authority_id"]


def _authority_status(tmp_path):
    active = tmp_path / "second_proof_authority" / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    return json.loads(active.read_text(encoding="utf-8"))["status"]


def test_retired_runner_block_is_not_a_broker_rejection(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")

    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["real_broker_contacted"] is False
    assert report["broker_rejected"] is False
    assert report["blocked_before_broker"] is True
    assert report["block_reason"] == RETIRED_REASON
    assert report["rejection_classification"]["category"] == "PRE_BROKER_GATE"
    assert calls == []


def test_retired_runner_block_preserves_lock_and_authority(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")

    aid = _authority_id(tmp_path)
    assert report["lock_consumed"] is False
    assert report["authority_still_active"] is True
    assert is_second_proof_lock_consumed(aid) is False
    assert _authority_status(tmp_path) == "active"
    assert calls == []


def test_retry_after_retired_runner_block_remains_safely_blocked(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    first = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert first["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"

    second = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    assert second["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    aid = _authority_id(tmp_path)
    assert is_second_proof_lock_consumed(aid) is False
    assert calls == []


def test_mocked_transport_rejection_cannot_bypass_retired_runner(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")

    assert report["verdict"] == "SECOND_PROOF_BLOCKED_BEFORE_BROKER"
    assert report["real_broker_contacted"] is False
    assert report["rejection_classification"]["category"] == "PRE_BROKER_GATE"
    aid = _authority_id(tmp_path)
    assert is_second_proof_lock_consumed(aid) is False
    assert _authority_status(tmp_path) == "active"
    assert calls == []


def test_evidence_report_carries_classification(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")

    from pathlib import Path

    evidence_file = Path(report["evidence_dir"]) / "SECOND_REAL_PROOF_EVIDENCE_REPORT.json"
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert evidence["broker_contacted"] is False
    assert evidence["rejection_classification"]["category"] == "PRE_BROKER_GATE"
    assert calls == []


def test_evidence_written_under_isolated_root(active_context, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(LiveBrokerFirewall, "submit_limit_order_adapter", _must_not_submit(calls))
    report = run_second_proof_execute_once(live_submit_path=tmp_path / "live_submit.json")
    # The autouse conftest fixture points DUMMY_EVIDENCE_ROOT at tmp_path/evidence.
    assert "artifacts" not in report["evidence_dir"].replace("\\", "/").split("/")[0]
    assert calls == []
