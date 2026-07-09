import json

import pytest

from core.kalshi_market_validator import ContractMetadata, MarketMetadata
from core.proof_order_candidate import (
    build_validated_proof_candidate,
    build_validated_proof_candidate_v2,
    safe_preview,
    write_candidate_packet_v2,
)


@pytest.fixture
def open_metadata():
    return MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ContractMetadata(
                ticker="KXBTC-26DEC25000-C", status="open", tradable=True
            )
        ],
    )


@pytest.fixture
def base_context():
    return {
        "descriptor_hash": "9A3A...3508",
        "caps_hash": "F7D9...E5B5",
        "live_submit_hash": "3875...515E",
        "evidence_registry_hash": "1C89...0113",
        "runtime_approval_hash": "ABCD...1234",
        "current_live_submit_hash": "EFGH...5678",
    }


def test_v2_candidate_core_fields(open_metadata, base_context):
    candidate = build_validated_proof_candidate_v2(
        open_metadata, proof_context=base_context
    )
    assert candidate.candidate_found is True
    assert candidate.price_validated is True
    assert candidate.order_type == "LIMIT"
    assert candidate.count == 1
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True
    assert candidate.price_source == "metadata"
    assert candidate.read_only_metadata_contact is True
    assert candidate.broker_submit_contact is False
    assert candidate.live_order_count == 0
    assert candidate.order_write_methods_blocked is True
    assert candidate.market_status == "open"
    assert candidate.contract_status == "open"
    assert candidate.market_tradable is True
    assert candidate.contract_tradable is True
    assert candidate.runtime_approval_hash == "ABCD...1234"
    assert candidate.current_live_submit_hash == "EFGH...5678"


def test_v2_proof_lock_consumed_reason(open_metadata):
    context = {"previous_real_broker_attempt_status": "BROKER_REJECTED"}
    candidate = build_validated_proof_candidate_v2(open_metadata, proof_context=context)
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True
    assert candidate.reason_submit_not_allowed == "PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED"
    assert candidate.proof_lock_status == "consumed_by_real_broker_attempt"
    assert candidate.previous_real_broker_attempt_recorded is True


def test_v2_packet_has_no_secrets(tmp_path, open_metadata, base_context):
    candidate = build_validated_proof_candidate_v2(
        open_metadata, proof_context=base_context
    )
    path = tmp_path / "VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json"
    write_candidate_packet_v2(candidate, path)
    raw = path.read_text(encoding="utf-8")
    lowered = raw.lower()
    assert "idempotency" not in lowered or "redacted" in lowered
    assert "private" not in lowered
    # `secrets_redacted` is a safe metadata flag, not a leaked secret value.
    assert "secret" not in lowered.replace("\"secrets_redacted\": true", "")
    data = json.loads(raw)
    assert data["secrets_redacted"] is True
    assert data["redacted"] is True


def test_v2_candidate_found_false_still_blocks_submit(open_metadata):
    candidate = build_validated_proof_candidate_v2(
        open_metadata, candidate_found=False
    )
    assert candidate.candidate_found is False
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True


def test_v1_builder_unchanged(open_metadata):
    caps = {"max_order_count": 1, "max_single_order_cents": 100}
    context = {"previous_real_broker_attempt_status": "BROKER_REJECTED"}
    candidate = build_validated_proof_candidate(open_metadata, caps, context)
    assert candidate.order_type == "LIMIT"
    assert candidate.count == 1
    assert candidate.price == 1
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True
    assert candidate.redacted is True


def test_safe_preview_includes_v2_fields_without_secrets(open_metadata, base_context):
    candidate = build_validated_proof_candidate_v2(
        open_metadata, proof_context=base_context
    )
    preview = safe_preview(candidate)
    assert preview["candidate_found"] is True
    assert preview["price_validated"] is True
    assert preview["market_tradable"] is True
    assert preview["contract_tradable"] is True
    assert "idempotency" not in preview
    assert "runtime_approval_hash" not in preview
    assert "current_live_submit_hash" not in preview
