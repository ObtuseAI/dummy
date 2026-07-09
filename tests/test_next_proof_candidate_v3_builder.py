"""Tests for the V3 proof candidate builder."""

from __future__ import annotations

from core.kalshi_market_validator import ContractMetadata, MarketMetadata
from core.proof_order_candidate import (
    build_validated_proof_candidate_v3,
    compute_candidate_hash,
    write_candidate_packet_v3,
)


def _open_metadata() -> MarketMetadata:
    return MarketMetadata(
        ticker="KXMVESPORTSMULTIGAMEEXTENDED-S2026ABCD-1234",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ContractMetadata(
                ticker="KXMVESPORTSMULTIGAMEEXTENDED-S2026ABCD-1234",
                status="open",
                tradable=True,
            )
        ],
    )


def test_v3_builder_sets_discovery_fields():
    candidate = build_validated_proof_candidate_v3(
        _open_metadata(),
        proof_context={"previous_real_broker_attempt_status": "BROKER_REJECTED"},
        candidate_found=True,
        discovery_mode="broad",
        get_request_count=1,
        response_schema_summary="keys:cursor,markets",
        candidate_selection_trace=["live_eligible_candidate_found"],
    )
    assert candidate.validation_mode == "read_only_discovery"
    assert candidate.discovery_mode == "broad"
    assert candidate.get_request_count == 1
    assert candidate.write_request_count == 0
    assert candidate.blocked_write_request_count == 0
    assert candidate.response_schema_summary == "keys:cursor,markets"
    assert candidate.candidate_selection_trace == ["live_eligible_candidate_found"]
    assert candidate.candidate_found is True
    assert candidate.market_tradable is True
    assert candidate.contract_tradable is True
    assert candidate.price_validated is True
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True
    assert candidate.order_type == "LIMIT"
    assert candidate.count == 1


def test_v3_builder_explicit_mode():
    candidate = build_validated_proof_candidate_v3(
        _open_metadata(),
        proof_context={"previous_real_broker_attempt_status": "BROKER_REJECTED"},
        candidate_found=True,
        discovery_mode="explicit",
        get_request_count=1,
        candidate_selection_trace=["explicit_candidate_valid"],
    )
    assert candidate.discovery_mode == "explicit"
    assert candidate.candidate_found is True


def test_v3_builder_blocked_candidate():
    candidate = build_validated_proof_candidate_v3(
        _open_metadata(),
        proof_context={"previous_real_broker_attempt_status": "BROKER_REJECTED"},
        candidate_found=False,
        price_validated=False,
        exact_blockers=["NO_TRADABLE_MARKETS"],
    )
    assert candidate.candidate_found is False
    assert candidate.price_validated is False
    assert candidate.exact_blockers == ["NO_TRADABLE_MARKETS"]


def test_v3_write_and_hash(tmp_path):
    candidate = build_validated_proof_candidate_v3(
        _open_metadata(),
        proof_context={"previous_real_broker_attempt_status": "BROKER_REJECTED"},
        candidate_found=True,
    )
    path = tmp_path / "candidate_v3.json"
    write_candidate_packet_v3(candidate, path)
    assert path.exists()
    h = compute_candidate_hash(path)
    assert len(h) == 64
    data = __import__("json").loads(path.read_text())
    assert data["validation_mode"] == "read_only_discovery"
    assert data["candidate_found"] is True
    assert data["submit_allowed_now"] is False
