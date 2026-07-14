"""Proof-order candidate builder.

Constructs a validated, no-submit candidate packet for the next real-broker
proof attempt. Never enables live-submit, never consumes proof lock.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.kalshi_market_validator import MarketMetadata, validate_payload_against_metadata


@dataclass(frozen=True)
class ProofCandidate:
    candidate_id: str
    created_at: str
    validation_mode: str
    market_ticker: str
    contract_ticker: str
    side: str
    count: int
    price: int
    cap_checks: dict[str, Any]
    market_metadata_checks: dict[str, Any]
    contract_metadata_checks: dict[str, Any]
    live_submit_required_hash: str | None
    descriptor_hash: str | None
    caps_hash: str | None
    evidence_registry_hash: str | None
    proof_lock_status: str
    submit_allowed_now: bool
    requires_new_operator_proof_authority: bool
    reason_submit_not_allowed: str
    redacted: bool
    action: str = "buy"
    order_type: str = "LIMIT"
    candidate_found: bool = False
    metadata_mode: str = "no_network"
    read_only_metadata_contact: bool = False
    broker_submit_contact: bool = False
    live_order_count: int = 0
    order_write_methods_blocked: bool = True
    market_status: str = "unknown"
    contract_status: str = "unknown"
    market_tradable: bool = False
    contract_tradable: bool = False
    price_source: str = "unknown"
    price_validated: bool = False
    previous_real_broker_attempt_recorded: bool = True
    no_submit_performed: bool = True
    no_cancel_performed: bool = True
    no_live_submit_mutation: bool = True
    secrets_redacted: bool = True
    runtime_approval_hash: str | None = None
    current_live_submit_hash: str | None = None
    discovery_mode: str = "broad"
    get_request_count: int = 0
    write_request_count: int = 0
    blocked_write_request_count: int = 0
    response_schema_summary: str = "unknown"
    candidate_selection_trace: list[str] = field(default_factory=list)
    exact_blockers: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_validated_proof_candidate(
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
    proof_context: dict[str, Any] | None = None,
    validation_mode: str = "no_network",
) -> ProofCandidate:
    """Build a candidate using the smallest valid proof size.

    The candidate is always produced, but `submit_allowed_now` is False if a
    previous real broker attempt is recorded in `proof_context`.
    """
    if caps is None:
        caps = {"max_order_count": 1, "max_single_order_cents": 100}
    elif hasattr(caps, "model_dump"):
        caps = caps.model_dump()
    elif not isinstance(caps, dict):
        caps = dict(caps)
    proof_context = proof_context or {}

    ticker = metadata.ticker.upper()
    contract = next(
        (c for c in metadata.contracts if c.ticker.upper() == ticker),
        metadata.contracts[0] if metadata.contracts else None,
    )
    contract_ticker = contract.ticker.upper() if contract else ticker

    # Smallest proof size: price at minimum allowed tick, count = 1.
    price = metadata.min_price_cents
    count = 1

    payload = {
        "ticker": ticker,
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": count,
        "price": price,
        "client_order_id": "<redacted_idempotency>",
    }

    validation = validate_payload_against_metadata(payload, metadata, caps)

    previous_status = proof_context.get("previous_real_broker_attempt_status")
    proof_lock_consumed = previous_status in {"BROKER_REJECTED", "BROKER_ACCEPTED"}

    reason = "previous real broker attempt recorded; new operator proof authority required"
    if proof_lock_consumed:
        proof_lock_status = "consumed_by_real_broker_attempt"
        submit_allowed = False
        requires_new_authority = True
    elif not validation.ok:
        proof_lock_status = "validation_failed"
        submit_allowed = False
        requires_new_authority = True
        reason = f"payload validation failed: {validation.error_message}"
    else:
        proof_lock_status = "clear"
        submit_allowed = False
        requires_new_authority = True
        reason = "live-submit disabled by default; explicit operator authority required"

    return ProofCandidate(
        candidate_id=f"candidate-{uuid.uuid4().hex[:16]}",
        created_at=_now_iso(),
        validation_mode=validation_mode,
        market_ticker=ticker,
        contract_ticker=contract_ticker,
        side="yes",
        action="buy",
        order_type="LIMIT",
        count=count,
        price=price,
        cap_checks={
            "max_order_count": caps.get("max_order_count", 1),
            "count": count,
            "count_ok": count <= caps.get("max_order_count", 1),
            "max_single_order_cents": caps.get("max_single_order_cents", 100),
            "order_value_cents": price * count,
        },
        market_metadata_checks={
            "ticker": metadata.ticker,
            "status": metadata.status,
            "trading_allowed": metadata.trading_allowed,
            "min_price_cents": metadata.min_price_cents,
            "max_price_cents": metadata.max_price_cents,
            "tick_size_cents": metadata.tick_size_cents,
        },
        contract_metadata_checks={
            "ticker": contract_ticker,
            "status": contract.status if contract else "unknown",
            "tradable": contract.tradable if contract else False,
        },
        live_submit_required_hash=proof_context.get("live_submit_hash"),
        descriptor_hash=proof_context.get("descriptor_hash"),
        caps_hash=proof_context.get("caps_hash"),
        evidence_registry_hash=proof_context.get("evidence_registry_hash"),
        proof_lock_status=proof_lock_status,
        submit_allowed_now=submit_allowed,
        requires_new_operator_proof_authority=requires_new_authority,
        reason_submit_not_allowed=reason,
        redacted=True,
    )


def build_validated_proof_candidate_v2(
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
    proof_context: dict[str, Any] | None = None,
    validation_mode: str = "read_only",
    candidate_found: bool = True,
    price_source: str = "metadata",
    price_validated: bool = True,
    read_only_metadata_contact: bool = True,
    broker_submit_contact: bool = False,
    live_order_count: int = 0,
    order_write_methods_blocked: bool = True,
) -> ProofCandidate:
    """Build a V2 candidate packet from read-only metadata.

    Always disables live-submit. Records proof-lock consumption when a prior
    real broker attempt exists in `proof_context`.
    """
    if caps is None:
        caps = {"max_order_count": 1, "max_single_order_cents": 100}
    elif hasattr(caps, "model_dump"):
        caps = caps.model_dump()
    elif not isinstance(caps, dict):
        caps = dict(caps)
    proof_context = proof_context or {}

    ticker = metadata.ticker.upper()
    contract = next(
        (c for c in metadata.contracts if c.ticker.upper() == ticker),
        metadata.contracts[0] if metadata.contracts else None,
    )
    contract_ticker = contract.ticker.upper() if contract else ticker

    price = metadata.min_price_cents if price_validated else 0
    count = 1

    payload = {
        "ticker": ticker,
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": count,
        "price": price,
        "client_order_id": "<redacted_idempotency>",
    }

    validation = validate_payload_against_metadata(payload, metadata, caps)

    previous_status = proof_context.get("previous_real_broker_attempt_status")
    proof_lock_consumed = previous_status in {"BROKER_REJECTED", "BROKER_ACCEPTED"}

    requires_new_authority = True
    if proof_lock_consumed:
        proof_lock_status = "consumed_by_real_broker_attempt"
        submit_allowed = False
        reason = "PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED"
    elif not validation.ok:
        proof_lock_status = "validation_failed"
        submit_allowed = False
        reason = f"payload validation failed: {validation.error_message}"
    else:
        proof_lock_status = "clear"
        submit_allowed = False
        reason = "live-submit disabled by default; explicit operator authority required"

    return ProofCandidate(
        candidate_id=f"candidate-{uuid.uuid4().hex[:16]}",
        created_at=_now_iso(),
        validation_mode=validation_mode,
        market_ticker=ticker,
        contract_ticker=contract_ticker,
        side="yes",
        action="buy",
        order_type="LIMIT",
        count=count,
        price=price,
        cap_checks={
            "max_order_count": caps.get("max_order_count", 1),
            "count": count,
            "count_ok": count <= caps.get("max_order_count", 1),
            "max_single_order_cents": caps.get("max_single_order_cents", 100),
            "order_value_cents": price * count,
        },
        market_metadata_checks={
            "ticker": metadata.ticker,
            "status": metadata.status,
            "trading_allowed": metadata.trading_allowed,
            "min_price_cents": metadata.min_price_cents,
            "max_price_cents": metadata.max_price_cents,
            "tick_size_cents": metadata.tick_size_cents,
        },
        contract_metadata_checks={
            "ticker": contract_ticker,
            "status": contract.status if contract else "unknown",
            "tradable": contract.tradable if contract else False,
        },
        live_submit_required_hash=proof_context.get("live_submit_hash"),
        descriptor_hash=proof_context.get("descriptor_hash"),
        caps_hash=proof_context.get("caps_hash"),
        evidence_registry_hash=proof_context.get("evidence_registry_hash"),
        proof_lock_status=proof_lock_status,
        submit_allowed_now=submit_allowed,
        requires_new_operator_proof_authority=requires_new_authority,
        reason_submit_not_allowed=reason,
        redacted=True,
        candidate_found=candidate_found,
        metadata_mode=validation_mode,
        read_only_metadata_contact=read_only_metadata_contact,
        broker_submit_contact=broker_submit_contact,
        live_order_count=live_order_count,
        order_write_methods_blocked=order_write_methods_blocked,
        market_status=metadata.status,
        contract_status=contract.status if contract else "unknown",
        market_tradable=metadata.trading_allowed,
        contract_tradable=contract.tradable if contract else False,
        price_source=price_source,
        price_validated=price_validated,
        previous_real_broker_attempt_recorded=proof_lock_consumed,
        no_submit_performed=True,
        no_cancel_performed=True,
        no_live_submit_mutation=True,
        secrets_redacted=True,
        runtime_approval_hash=proof_context.get("runtime_approval_hash"),
        current_live_submit_hash=proof_context.get("current_live_submit_hash"),
    )


def safe_preview(candidate: ProofCandidate) -> dict[str, Any]:
    """Return a secret-free, human-readable preview."""
    return {
        "candidate_id": candidate.candidate_id,
        "created_at": candidate.created_at,
        "validation_mode": candidate.validation_mode,
        "market_ticker": candidate.market_ticker,
        "contract_ticker": candidate.contract_ticker,
        "side": candidate.side,
        "action": candidate.action,
        "order_type": candidate.order_type,
        "count": candidate.count,
        "price_cents": candidate.price,
        "submit_allowed_now": candidate.submit_allowed_now,
        "requires_new_operator_proof_authority": candidate.requires_new_operator_proof_authority,
        "reason_submit_not_allowed": candidate.reason_submit_not_allowed,
        "proof_lock_status": candidate.proof_lock_status,
        "redacted": candidate.redacted,
        "candidate_found": candidate.candidate_found,
        "metadata_mode": candidate.metadata_mode,
        "read_only_metadata_contact": candidate.read_only_metadata_contact,
        "broker_submit_contact": candidate.broker_submit_contact,
        "live_order_count": candidate.live_order_count,
        "order_write_methods_blocked": candidate.order_write_methods_blocked,
        "market_status": candidate.market_status,
        "contract_status": candidate.contract_status,
        "market_tradable": candidate.market_tradable,
        "contract_tradable": candidate.contract_tradable,
        "price_source": candidate.price_source,
        "price_validated": candidate.price_validated,
        "previous_real_broker_attempt_recorded": candidate.previous_real_broker_attempt_recorded,
        "no_submit_performed": candidate.no_submit_performed,
        "no_cancel_performed": candidate.no_cancel_performed,
        "no_live_submit_mutation": candidate.no_live_submit_mutation,
        "secrets_redacted": candidate.secrets_redacted,
        "discovery_mode": candidate.discovery_mode,
        "get_request_count": candidate.get_request_count,
        "write_request_count": candidate.write_request_count,
        "blocked_write_request_count": candidate.blocked_write_request_count,
        "response_schema_summary": candidate.response_schema_summary,
        "candidate_selection_trace": candidate.candidate_selection_trace,
        "exact_blockers": candidate.exact_blockers,
    }


def write_candidate_packet(candidate: ProofCandidate, path: str | os.PathLike[str]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(candidate)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return p


def write_candidate_packet_v2(candidate: ProofCandidate, path: str | os.PathLike) -> Path:
    """Write the full V2 candidate packet, including all new safe fields."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(candidate)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return p


def build_validated_proof_candidate_v3(
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
    proof_context: dict[str, Any] | None = None,
    candidate_found: bool = True,
    price_source: str = "metadata",
    price_validated: bool = True,
    read_only_metadata_contact: bool = True,
    broker_submit_contact: bool = False,
    live_order_count: int = 0,
    order_write_methods_blocked: bool = True,
    discovery_mode: str = "broad",
    get_request_count: int = 0,
    write_request_count: int = 0,
    blocked_write_request_count: int = 0,
    response_schema_summary: str = "unknown",
    candidate_selection_trace: list[str] | None = None,
    exact_blockers: list[str] | None = None,
) -> ProofCandidate:
    """Build a V3 discovery candidate packet from read-only metadata."""
    candidate = build_validated_proof_candidate_v2(
        metadata,
        caps,
        proof_context,
        validation_mode="read_only_discovery",
        candidate_found=candidate_found,
        price_source=price_source,
        price_validated=price_validated,
        read_only_metadata_contact=read_only_metadata_contact,
        broker_submit_contact=broker_submit_contact,
        live_order_count=live_order_count,
        order_write_methods_blocked=order_write_methods_blocked,
    )
    # Replace immutable dataclass with a new one carrying V3 fields.
    v3_data = asdict(candidate)
    v3_data.update({
        "validation_mode": "read_only_discovery",
        "discovery_mode": discovery_mode,
        "get_request_count": get_request_count,
        "write_request_count": write_request_count,
        "blocked_write_request_count": blocked_write_request_count,
        "response_schema_summary": response_schema_summary,
        "candidate_selection_trace": candidate_selection_trace or [],
        "exact_blockers": exact_blockers or [],
    })
    return ProofCandidate(**v3_data)


def write_candidate_packet_v3(candidate: ProofCandidate, path: str | os.PathLike) -> Path:
    """Write the full V3 discovery candidate packet."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(candidate)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return p


def compute_candidate_hash(path: str | os.PathLike[str]) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
