"""Tests for the activate-second-proof-authority command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.proof_authority import REQUIRED_CONFIRMATION
from tools.operator_authority_appliance import operator_full_completion as ofc


@pytest.fixture
def prepared_context(tmp_path, monkeypatch):
    """Patch paths, write valid artifacts, and run prepare to create a draft."""
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

    # Run prepare to create draft.
    import io
    out = io.StringIO()
    args = ofc.build_parser().parse_args(["prepare-second-proof-authority"])
    rc = ofc.cmd_prepare_second_proof_authority(args, out)
    assert rc == ofc.EXIT_OK
    return tmp_path


def _run_activate(tmp_path, confirm=REQUIRED_CONFIRMATION, operator="chris", reason="second controlled proof", expires="2099-01-01T00:00:00Z"):
    import io
    out = io.StringIO()
    args = ofc.build_parser().parse_args([
        "activate-second-proof-authority",
        "--operator-name", operator,
        "--reason", reason,
        "--expires-at", expires,
        "--confirm", confirm,
    ])
    rc = ofc.cmd_activate_second_proof_authority(args, out)
    return rc, json.loads(out.getvalue())


def test_exact_confirmation_writes_active_file(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "SECOND_PROOF_AUTHORITY_ACTIVE"
    assert report["authority_id"]
    active_path = Path(report["active_path"])
    assert active_path.exists()
    data = json.loads(active_path.read_text(encoding="utf-8"))
    assert data["status"] == "active"
    assert data["operator_name"] == "chris"


def test_missing_confirmation_blocks(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path, confirm="")
    assert rc == ofc.EXIT_MISSING
    assert report["verdict"] == "BLOCKED_CONFIRMATION_MISMATCH"


def test_wrong_confirmation_blocks(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path, confirm="I approve something else")
    assert rc == ofc.EXIT_MISSING
    assert report["verdict"] == "BLOCKED_CONFIRMATION_MISMATCH"


def test_activation_does_not_run_one_shot_live(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["no_live_proof_run"] is True


def test_activation_does_not_contact_broker(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["no_broker_contact"] is True


def test_activation_preserves_old_proof_registry(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    from core import proof_authority as pa
    registry = json.loads(pa.REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert registry["latest_real_broker_attempt_status"] == "BROKER_REJECTED"
    assert registry["latest_real_broker_contacted"] is True
    assert registry["evidence_index_hash"] == "1C895591A874389AA3855A281B856EE239F920579DC04564B949940CCCF10113"


def test_activation_creates_second_proof_lock_namespace(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    lock_path = Path(report["lock_path"])
    assert lock_path.exists()
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    assert data["consumed"] is False
    assert data["authority_id"] == report["authority_id"]


def test_activation_scopes_live_submit(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    from core import proof_authority as pa
    live_submit = json.loads(pa.LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
    assert live_submit["enabled"] is True
    assert live_submit["proof_scope"] == "one_controlled_proof"
    assert live_submit["second_proof_authority_id"] == report["authority_id"]
    assert live_submit["market_orders_allowed"] is False
    assert live_submit.get("scale_enabled") is not True
    assert live_submit.get("autonomy_enabled") is not True


def test_activation_creates_backup(prepared_context, tmp_path):
    rc, report = _run_activate(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["backup_path"]
    assert Path(report["backup_path"]).exists()


def test_activation_blocks_if_draft_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ofc, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    import io
    out = io.StringIO()
    args = ofc.build_parser().parse_args([
        "activate-second-proof-authority",
        "--operator-name", "chris",
        "--reason", "test",
        "--expires-at", "2099-01-01T00:00:00Z",
        "--confirm", REQUIRED_CONFIRMATION,
    ])
    rc = ofc.cmd_activate_second_proof_authority(args, out)
    assert rc == ofc.EXIT_SAFETY
    report = json.loads(out.getvalue())
    assert report["verdict"] == "BLOCKED_SECOND_PROOF_AUTHORITY"
    assert report["reason"] == "DRAFT_MISSING"
