"""Tests for the prepare-second-proof-authority command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.operator_authority_appliance import operator_full_completion as ofc


@pytest.fixture
def valid_context(tmp_path, monkeypatch):
    """Patch paths used by the prepare command and write valid artifacts."""
    from core import proof_authority as pa
    monkeypatch.setattr(pa, "V3_CANDIDATE_PATH", tmp_path / "v3.json")
    monkeypatch.setattr(pa, "V3_REPORT_PATH", tmp_path / "v3_report.json")
    monkeypatch.setattr(pa, "REAL_PROOF_REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(pa, "CAPS_PATH", tmp_path / "caps.json")
    monkeypatch.setattr(pa, "ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")
    monkeypatch.setattr(pa, "LIVE_SUBMIT_PATH", tmp_path / "live_submit.json")
    monkeypatch.setattr(pa, "RUNTIME_APPROVALS_DIR", tmp_path / "approvals")
    monkeypatch.setattr(pa, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")
    monkeypatch.setattr(ofc, "SECOND_PROOF_AUTHORITY_DIR", tmp_path / "second_proof_authority")

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


def _run_prepare(tmp_path):
    import io
    out = io.StringIO()
    args = ofc.build_parser().parse_args(["prepare-second-proof-authority"])
    rc = ofc.cmd_prepare_second_proof_authority(args, out)
    return rc, json.loads(out.getvalue())


def test_valid_v3_candidate_creates_draft(valid_context, tmp_path):
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["verdict"] == "SECOND_PROOF_AUTHORITY_DRAFT_READY"
    assert report["draft_created"] is True
    assert report["authority_active"] is False
    assert report["submit_allowed_now"] is False
    assert report["reason_submit_not_allowed"] == "SECOND_PROOF_AUTHORITY_NOT_ACTIVE"
    assert report["broker_contact"] is False
    assert report["live_order_count"] == 0
    draft_path = Path(report["draft_path"])
    assert draft_path.exists()


def test_candidate_found_false_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["candidate_found"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert report["verdict"] == "BLOCKED_SECOND_PROOF_AUTHORITY"
    assert report["draft_created"] is False
    assert "BLOCKED_CANDIDATE_NOT_FOUND" in report["reason_submit_not_allowed"]


def test_price_not_validated_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["price_validated"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert "BLOCKED_PRICE_NOT_VALIDATED" in report["reason_submit_not_allowed"]


def test_market_not_tradable_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["market_tradable"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert "BLOCKED_MARKET_NOT_TRADABLE" in report["reason_submit_not_allowed"]


def test_contract_not_tradable_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["contract_tradable"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert "BLOCKED_CONTRACT_NOT_TRADABLE" in report["reason_submit_not_allowed"]


def test_old_proof_registry_missing_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    pa.REAL_PROOF_REGISTRY_PATH.unlink()
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert "BLOCKED_PRIOR_PROOF_REGISTRY_INVALID" in report["reason_submit_not_allowed"]


def test_old_proof_lock_not_consumed_blocks(valid_context, tmp_path):
    from core import proof_authority as pa
    registry = json.loads(pa.REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["latest_real_broker_contacted"] = False
    pa.REAL_PROOF_REGISTRY_PATH.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_SAFETY
    assert "BLOCKED_PRIOR_PROOF_LOCK_NOT_CONSUMED" in report["reason_submit_not_allowed"]


def test_prepare_does_not_enable_live_submit(valid_context, tmp_path):
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_OK
    from core import proof_authority as pa
    live_submit = json.loads(pa.LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
    assert live_submit.get("enabled") is False


def test_prepare_does_not_contact_broker(valid_context, tmp_path):
    rc, report = _run_prepare(tmp_path)
    assert rc == ofc.EXIT_OK
    assert report["broker_contact"] is False
    assert report["live_order_count"] == 0
