"""Second-proof execution runner.

Encapsulates exactly one controlled real-broker proof attempt using the active
second-proof authority and the validated V3 candidate, routed through
LiveBrokerFirewall. This module is importable for tests and is also invoked by
the CLI script.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kalshi.rejection_classifier import classify_rejection
from core.ontology import LiveOrderResult
from core.proof_authority import (
    SECOND_PROOF_AUTHORITY_DIR,
    V3_CANDIDATE_PATH,
    SecondProofAuthority,
    SecondProofAuthorityStatus,
    authority_from_dict,
    authority_to_dict,
    mark_authority_used,
)
from core.second_proof_lock import consume_second_proof_lock, is_second_proof_lock_consumed
from predator_mesh.brokers import LimitOrderRequest


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _idempotency_key(authority_id: str, nonce: str) -> str:
    return hashlib.sha256(f"{authority_id}|{nonce}".encode("utf-8")).hexdigest()[:32]


def _build_limit_order_request(authority: SecondProofAuthority) -> LimitOrderRequest:
    idem = _idempotency_key(authority.authority_id, datetime.now(timezone.utc).isoformat())
    return LimitOrderRequest(
        venue="KALSHI",
        order_type="LIMIT",
        market_orders_allowed=False,
        side="yes",
        action="buy",
        price=authority.candidate_price,
        quantity=authority.candidate_count,
        idempotency_key=idem,
        market_ticker=authority.candidate_market_ticker,
        proof_id=authority.authority_id,
        proof_target="SECOND_CONTROLLED_REAL_BROKER_PROOF",
        client_order_id=idem,
        max_order_count=1,
        max_order_size_cents=100,
    )


def _evidence_root() -> Path:
    """Evidence root, overridable so tests never pollute real artifacts."""
    return Path(os.environ.get("DUMMY_EVIDENCE_ROOT", "artifacts/dummy"))


def _write_evidence(
    authority: SecondProofAuthority,
    result: Any,
    broker_contacted: bool,
    accepted: bool,
    rejected: bool,
    classification: dict[str, Any] | None = None,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    evidence_dir = _evidence_root() / f"second_real_proof_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    broker_order_id = getattr(result, "order_id", None) if accepted else None
    safe_report = {
        "verdict": "SECOND_PROOF_EXECUTED_ACCEPTED" if accepted else "SECOND_PROOF_EXECUTED_BROKER_REJECTED" if rejected else "SECOND_PROOF_BLOCKED_BEFORE_BROKER",
        "authority_id": authority.authority_id,
        "candidate_market_ticker": authority.candidate_market_ticker,
        "candidate_contract_ticker": authority.candidate_contract_ticker,
        "candidate_price": authority.candidate_price,
        "candidate_count": authority.candidate_count,
        "candidate_order_type": authority.candidate_order_type,
        "candidate_hash": authority.candidate_hash,
        "broker_contacted": broker_contacted,
        "real_live_orders_submitted_count": 1 if accepted else 0,
        "broker_accepted": accepted,
        "broker_rejected": rejected,
        "broker_order_id": broker_order_id or "",
        "broker_rejection_code": getattr(result, "broker_rejection_code", "") if rejected else "",
        "broker_rejection_safe_message": getattr(result, "broker_rejection_safe_message", "") if rejected else "",
        "broker_rejection_http_status": getattr(result, "broker_rejection_http_status", "") if rejected else "",
        "broker_rejection_adapter_error_type": getattr(result, "broker_rejection_adapter_error_type", "") if rejected else "",
        "broker_rejection_stage": getattr(result, "broker_rejection_stage", "") if rejected else "",
        "market_order_submitted": False,
        "scale_enabled": False,
        "autonomy_enabled": False,
        "evidence_dir": str(evidence_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "secrets_redacted": True,
        "rejection_classification": classification,
    }
    (evidence_dir / "SECOND_REAL_PROOF_EVIDENCE_REPORT.json").write_text(
        json.dumps(safe_report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return evidence_dir


def restore_live_submit_disabled_default(live_submit_path: Path | None = None) -> None:
    """Restore live-submit to the safe disabled default after a second proof."""
    live_submit_path = live_submit_path or Path("configs/live_submit.json")
    if not live_submit_path.exists():
        return
    disabled = {
        "enabled": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": "second_proof_completed_auto_relock",
    }
    live_submit_path.write_text(json.dumps(disabled, indent=2, sort_keys=True), encoding="utf-8")


def run_second_proof_execute_once(
    active_path: Path | None = None,
    firewall_factory: Any | None = None,
    live_submit_path: Path | None = None,
) -> dict[str, Any]:
    """Run exactly one second-proof live attempt and return the result report.

    Args:
        active_path: Override path to the active authority file (tests only).
        firewall_factory: Deprecated compatibility argument. It is never
            invoked because the legacy proof runner no longer owns a broker
            write path.
    """
    active_path = active_path or (SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json")
    if not active_path.exists():
        return {"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": "ACTIVE_AUTHORITY_MISSING"}

    data = _load_json(active_path)
    try:
        authority = authority_from_dict(data)
    except Exception as exc:
        return {"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": f"INVALID_ACTIVE_AUTHORITY:{type(exc).__name__}"}

    if authority.status != SecondProofAuthorityStatus.ACTIVE:
        return {"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": "AUTHORITY_NOT_ACTIVE"}

    if is_second_proof_lock_consumed(authority.authority_id):
        return {"verdict": "BLOCKED_SECOND_PROOF_LOCK_ALREADY_USED"}

    current_candidate_hash = _sha256_file(V3_CANDIDATE_PATH)
    if authority.candidate_hash != current_candidate_hash:
        return {"verdict": "BLOCKED_CANDIDATE_HASH_MISMATCH"}

    del firewall_factory
    result = LiveOrderResult(
        success=False,
        error="LEGACY_SECOND_PROOF_RUNNER_RETIRED_USE_CENTRAL_FIREWALL",
        proof_reference=authority.authority_id,
        broker_contacted=False,
    )

    accepted = bool(getattr(result, "success", False) and getattr(result, "order_id", None))

    # Broker contact requires transport evidence (HTTP status or the
    # broker_transport stage marker). Local firewall/gate blocks are
    # classified pre-broker and must not be reported as broker rejections.
    classification = None
    if not accepted:
        classification = classify_rejection(
            error_code=str(getattr(result, "error", "") or ""),
            http_status=getattr(result, "broker_rejection_http_status", None),
            safe_message=getattr(result, "broker_rejection_safe_message", None),
            stage=getattr(result, "broker_rejection_stage", None),
        )

    rejected = bool(not accepted and classification is not None and classification.broker_contacted)
    broker_contacted = accepted or rejected
    blocked_before_broker = not broker_contacted

    if broker_contacted:
        # The single real attempt was spent: consume the lock and retire the
        # authority regardless of accept/reject.
        lock_result = {
            "broker_contacted": broker_contacted,
            "accepted": accepted,
            "rejected": rejected,
            "reason": str(result.error) if rejected else "accepted",
            "broker_order_id": getattr(result, "order_id", None),
            "broker_rejection_code": getattr(result, "broker_rejection_code", "") if rejected else "",
            "rejection_classification": classification.to_dict() if classification else None,
        }
        consume_second_proof_lock(authority.authority_id, lock_result)

    evidence_dir = _write_evidence(
        authority,
        result,
        broker_contacted,
        accepted,
        rejected,
        classification.to_dict() if classification else None,
    )

    if broker_contacted:
        used_authority = mark_authority_used(authority)
        active_path.write_text(json.dumps(authority_to_dict(used_authority), indent=2, sort_keys=True), encoding="utf-8")

    restore_live_submit_disabled_default(live_submit_path)

    return {
        "verdict": "SECOND_PROOF_EXECUTED_ACCEPTED" if accepted else "SECOND_PROOF_EXECUTED_BROKER_REJECTED" if rejected else "SECOND_PROOF_BLOCKED_BEFORE_BROKER",
        "authority_id": authority.authority_id,
        "real_broker_contacted": broker_contacted,
        "broker_contact_witness": (
            "order_id" if accepted else classification.matched_on if classification else "none"
        ),
        "real_live_orders_submitted_count": 1 if accepted else 0,
        "broker_accepted": accepted,
        "broker_rejected": rejected,
        "blocked_before_broker": blocked_before_broker,
        "block_reason": (str(getattr(result, "error", "") or "") if blocked_before_broker else None),
        "rejection_classification": classification.to_dict() if classification else None,
        "authority_still_active": blocked_before_broker,
        "lock_consumed": broker_contacted,
        "market_order_submitted": False,
        "evidence_dir": str(evidence_dir),
        "live_submit_restored_disabled": True,
    }
