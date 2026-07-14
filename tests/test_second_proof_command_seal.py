"""Tests for command seal / one-shot-check second-proof state handling."""

from __future__ import annotations

import io
import json

import pytest

from core.proof_authority import REQUIRED_CONFIRMATION
from tools.operator_authority_appliance import operator_full_completion as ofc


@pytest.fixture
def base_context(tmp_path, monkeypatch):
    """Patch paths and write valid first-proof + V3 artifacts."""
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
    return tmp_path


def _run_one_shot_check(tmp_path, env=None):
    import io
    out = io.StringIO()
    rc = ofc.cmd_one_shot_check(env or {}, None, out)
    return rc, json.loads(out.getvalue())


def test_default_disabled_state_blocked(base_context, tmp_path):
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "BLOCKED_LIVE_SUBMIT_CAPS"


def test_second_proof_draft_ready(base_context, tmp_path):
    # Create draft.
    args = ofc.build_parser().parse_args(["prepare-second-proof-authority"])
    ofc.cmd_prepare_second_proof_authority(args, io.StringIO())
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "SECOND_PROOF_AUTHORITY_DRAFT_READY"


def test_second_proof_active_env_gate_required(base_context, tmp_path, monkeypatch):
    # Create and activate draft.
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
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "SECOND_PROOF_READY_ENV_GATE_REQUIRED"


def test_second_proof_active_env_present_ready(base_context, tmp_path, monkeypatch):
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
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    rc, report = _run_one_shot_check(tmp_path, env=env)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "READY_FOR_LIVE_PROOF"


def test_candidate_hash_mismatch_blocks(base_context, tmp_path, monkeypatch):
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
    # Tamper with candidate after activation.
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["price"] = 99
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "BLOCKED_CANDIDATE_HASH_MISMATCH"


def test_caps_mismatch_blocks(base_context, tmp_path, monkeypatch):
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
    from core import proof_authority as pa
    caps = json.loads(pa.CAPS_PATH.read_text(encoding="utf-8"))
    caps["max_order_count"] = 5
    pa.CAPS_PATH.write_text(json.dumps(caps, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "BLOCKED_CAPS_HASH_MISMATCH"


def test_descriptor_mismatch_blocks(base_context, tmp_path, monkeypatch):
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
    from core import proof_authority as pa
    desc = json.loads(pa.ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    desc["broker"] = "OTHER"
    pa.ADAPTER_DESCRIPTOR_PATH.write_text(json.dumps(desc, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(ofc, "_seal_status", lambda: "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT")
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "BLOCKED_DESCRIPTOR_HASH_MISMATCH"


def test_old_authority_repeat_blocked(base_context, tmp_path, monkeypatch):
    # Simulate first proof lock still present and no second authority.
    monkeypatch.setattr(ofc, "_proof_lock", lambda: True)
    rc, report = _run_one_shot_check(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "BLOCKED_LIVE_SUBMIT_CAPS"
