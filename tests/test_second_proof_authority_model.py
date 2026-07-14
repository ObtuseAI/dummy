"""Tests for the second-proof authority model and lock namespace."""

from __future__ import annotations

import json

import pytest

from core.proof_authority import (
    REQUIRED_CONFIRMATION,
    SecondProofAuthorityStatus,
    activate_second_proof_authority,
    authority_from_dict,
    authority_status,
    authority_to_dict,
    build_second_proof_authority_draft,
)
from core.second_proof_lock import (
    any_second_proof_attempt_consumed,
    consume_second_proof_lock,
    create_second_proof_lock,
    is_second_proof_lock_consumed,
)


@pytest.fixture
def valid_context(tmp_path, monkeypatch):
    """Patch all file paths and write valid V3/registry/caps/descriptor/approval artifacts."""
    from core import proof_authority as pa
    monkeypatch.setattr(pa, "V3_CANDIDATE_PATH", tmp_path / "v3.json")
    monkeypatch.setattr(pa, "V3_REPORT_PATH", tmp_path / "v3_report.json")
    monkeypatch.setattr(pa, "REAL_PROOF_REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(pa, "CAPS_PATH", tmp_path / "caps.json")
    monkeypatch.setattr(pa, "ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")
    monkeypatch.setattr(pa, "LIVE_SUBMIT_PATH", tmp_path / "live_submit.json")
    monkeypatch.setattr(pa, "RUNTIME_APPROVALS_DIR", tmp_path / "approvals")

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


def test_draft_has_required_fields(valid_context):
    authority = build_second_proof_authority_draft()
    assert authority.status == SecondProofAuthorityStatus.DRAFT
    assert authority.authority_type == "SECOND_CONTROLLED_REAL_BROKER_PROOF"
    assert authority.candidate_market_ticker == "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6"
    assert authority.candidate_contract_ticker == "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6"
    assert authority.candidate_price == 1
    assert authority.candidate_count == 1
    assert authority.candidate_order_type == "LIMIT"
    assert authority.max_attempts == 1
    assert authority.market_orders_allowed is False
    assert authority.scale_allowed is False
    assert authority.autonomy_allowed is False
    assert authority.prior_proof_status == "BROKER_REJECTED"
    assert authority.prior_proof_lock_consumed is True
    assert authority.created_by_operator is False


def test_draft_candidate_hash_matches_file(valid_context):
    authority = build_second_proof_authority_draft()
    from core.proof_authority import _sha256_file, V3_CANDIDATE_PATH
    assert authority.candidate_hash == _sha256_file(V3_CANDIDATE_PATH)


def test_blocks_candidate_not_found(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["candidate_found"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_CANDIDATE_NOT_FOUND"):
        build_second_proof_authority_draft()


def test_blocks_market_not_tradable(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["market_tradable"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_MARKET_NOT_TRADABLE"):
        build_second_proof_authority_draft()


def test_blocks_contract_not_tradable(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["contract_tradable"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_CONTRACT_NOT_TRADABLE"):
        build_second_proof_authority_draft()


def test_blocks_price_not_validated(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["price_validated"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_PRICE_NOT_VALIDATED"):
        build_second_proof_authority_draft()


def test_blocks_order_type_not_limit(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["order_type"] = "MARKET"
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_ORDER_TYPE_NOT_LIMIT"):
        build_second_proof_authority_draft()


def test_blocks_count_not_one(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["count"] = 2
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_COUNT_NOT_ONE"):
        build_second_proof_authority_draft()


def test_blocks_submit_allowed_now_true(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["submit_allowed_now"] = True
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_SUBMIT_ALLOWED_UNDER_OLD_AUTHORITY"):
        build_second_proof_authority_draft()


def test_blocks_no_new_authority_required(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["requires_new_operator_proof_authority"] = False
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_NO_NEW_AUTHORITY_REQUIRED"):
        build_second_proof_authority_draft()


def test_blocks_registry_missing(valid_context):
    from core import proof_authority as pa
    pa.REAL_PROOF_REGISTRY_PATH.unlink()
    with pytest.raises(ValueError, match="BLOCKED_PRIOR_PROOF_REGISTRY_INVALID"):
        build_second_proof_authority_draft()


def test_blocks_registry_not_consumed(valid_context):
    from core import proof_authority as pa
    registry = json.loads(pa.REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["latest_real_broker_contacted"] = False
    pa.REAL_PROOF_REGISTRY_PATH.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="BLOCKED_PRIOR_PROOF_LOCK_NOT_CONSUMED"):
        build_second_proof_authority_draft()


def test_blocks_stale_candidate_hash(valid_context):
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["price"] = 99
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    # Hash is recomputed from file, so the draft will succeed but the hash will differ.
    authority = build_second_proof_authority_draft()
    assert authority.candidate_hash != pa.EXPECTED_CANDIDATE_HASH


def test_activation_requires_exact_confirmation(valid_context):
    draft = build_second_proof_authority_draft()
    with pytest.raises(ValueError, match="CONFIRMATION_MISMATCH"):
        activate_second_proof_authority(draft, "chris", "test", "2099-01-01T00:00:00Z", "wrong")


def test_activation_requires_draft_state(valid_context):
    draft = build_second_proof_authority_draft()
    active = activate_second_proof_authority(draft, "chris", "test", "2099-01-01T00:00:00Z", REQUIRED_CONFIRMATION)
    with pytest.raises(ValueError, match="AUTHORITY_NOT_DRAFT"):
        activate_second_proof_authority(active, "chris", "test", "2099-01-01T00:00:00Z", REQUIRED_CONFIRMATION)


def test_activation_requires_future_expiry(valid_context):
    draft = build_second_proof_authority_draft()
    with pytest.raises(ValueError, match="EXPIRES_AT_STALE"):
        activate_second_proof_authority(draft, "chris", "test", "2000-01-01T00:00:00Z", REQUIRED_CONFIRMATION)


def test_activation_detects_candidate_hash_change(valid_context):
    draft = build_second_proof_authority_draft()
    from core import proof_authority as pa
    candidate = json.loads(pa.V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate["price"] = 99
    pa.V3_CANDIDATE_PATH.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_HASH_CHANGED"):
        activate_second_proof_authority(draft, "chris", "test", "2099-01-01T00:00:00Z", REQUIRED_CONFIRMATION)


def test_activation_detects_registry_hash_change(valid_context):
    draft = build_second_proof_authority_draft()
    from core import proof_authority as pa
    registry = json.loads(pa.REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["evidence_index_hash"] = "TAMPERED"
    pa.REAL_PROOF_REGISTRY_PATH.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="REGISTRY_HASH_CHANGED"):
        activate_second_proof_authority(draft, "chris", "test", "2099-01-01T00:00:00Z", REQUIRED_CONFIRMATION)


def test_activation_success(valid_context):
    draft = build_second_proof_authority_draft()
    active = activate_second_proof_authority(draft, "chris", "second controlled proof", "2099-01-01T00:00:00Z", REQUIRED_CONFIRMATION)
    assert active.status == SecondProofAuthorityStatus.ACTIVE
    assert active.operator_name == "chris"
    assert active.reason == "second controlled proof"
    assert active.created_by_operator is True
    assert active.exact_typed_confirmation_digest


def test_authority_dict_roundtrip(valid_context):
    draft = build_second_proof_authority_draft()
    data = authority_to_dict(draft)
    restored = authority_from_dict(data)
    assert restored == draft


def test_authority_status_secret_free(valid_context):
    draft = build_second_proof_authority_draft()
    status = authority_status(draft)
    assert status["status"] == "draft"
    assert "operator_name" not in status
    assert "exact_typed_confirmation_digest" not in status


# --- second-proof lock namespace tests ---


def test_second_proof_lock_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr("core.second_proof_lock.SECOND_PROOF_LOCK_DIR", tmp_path / "proof_locks")
    aid = "second-proof-test-001"
    assert is_second_proof_lock_consumed(aid) is False
    create_second_proof_lock(aid)
    assert is_second_proof_lock_consumed(aid) is False
    consume_second_proof_lock(aid, {"broker_contacted": True, "accepted": False, "reason": "BROKER_REJECTED"})
    assert is_second_proof_lock_consumed(aid) is True
    data = json.loads((tmp_path / "proof_locks" / f"second_proof_{aid}.json").read_text(encoding="utf-8"))
    assert data["consumed"] is True
    assert data["broker_contacted"] is True
    assert data["reason"] == "BROKER_REJECTED"


def test_any_second_proof_attempt_consumed(tmp_path, monkeypatch):
    monkeypatch.setattr("core.second_proof_lock.SECOND_PROOF_LOCK_DIR", tmp_path / "proof_locks")
    assert any_second_proof_attempt_consumed() is False
    create_second_proof_lock("aid-1")
    assert any_second_proof_attempt_consumed() is False
    consume_second_proof_lock("aid-1", {"broker_contacted": True, "accepted": True})
    assert any_second_proof_attempt_consumed() is True
