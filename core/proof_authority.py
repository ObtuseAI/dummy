"""Second-proof authority model for controlled real-broker retry.

This module is intentionally separate from the first-proof authority path so
that a second controlled proof attempt can be tracked in its own namespace
without erasing or reusing the first consumed proof lock.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from core.caps_authority import (
    CAPS_AUTHORITY_REGISTRATION_PATH as DEFAULT_CAPS_AUTHORITY_REGISTRATION_PATH,
    CURRENT_CAPS_AUTHORITY_EPOCH,
    CURRENT_CAPS_SCHEMA_VERSION,
    LEGACY_CAPS_SHA256,
    PROTECTED_CAPS_SHA256,
    evaluate_caps_authority,
)

V3_CANDIDATE_PATH = Path("artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json")
V3_REPORT_PATH = Path("artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json")
REAL_PROOF_REGISTRY_PATH = Path("artifacts/dummy/real_proof_registry.json")
CAPS_PATH = Path("configs/caps.json")
CAPS_AUTHORITY_REGISTRATION_PATH = DEFAULT_CAPS_AUTHORITY_REGISTRATION_PATH
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")

# How long a validated candidate's market observation stays trustworthy.
# Every other candidate invariant reads a boolean captured at validation time,
# so without an age bound a stale packet asserts a market state that may be
# hours or weeks out of date. One hour suits an operator-driven ceremony: long
# enough to walk the runbook, short enough that the market has not moved on.
CANDIDATE_MAX_AGE_SECONDS = 3600
LIVE_SUBMIT_PATH = Path("configs/live_submit.json")
RUNTIME_APPROVALS_DIR = Path("runtime/approvals")
SECOND_PROOF_AUTHORITY_DIR = Path("artifacts/dummy/second_proof_authority")
SECOND_PROOF_LOCK_DIR = Path("runtime/proof_locks")

# Hashes from the validated V3 read-only discovery candidate and its context.
EXPECTED_CANDIDATE_HASH = "937EDB874832F4AAFD9A421E0A13AA781DB2965C79C0A3BBD3FC5C1B4C9C9B85"
EXPECTED_REGISTRY_HASH = "1C895591A874389AA3855A281B856EE239F920579DC04564B949940CCCF10113"
EXPECTED_CAPS_HASH = PROTECTED_CAPS_SHA256
EXPECTED_DESCRIPTOR_HASH = "9A3A4ABF56B7BDE9BD84901127A036C8C5A278BB49046B53A1D8AE1B96473508"
EXPECTED_RUNTIME_APPROVAL_HASH = "726BA607F30462EFAC8A22D43DD515EDF18F4C7DB97DA8F47A51C37D89F99D15"
EXPECTED_LIVE_SUBMIT_DISABLED_HASH = "3875B81E90B636147CC5BCE5F247B71AD25877C165F4773C98D5C2AD61DB515E"
SECOND_PROOF_AUTHORITY_SCHEMA_VERSION = 2

# Exact operator confirmation required to activate a second controlled proof.
REQUIRED_CONFIRMATION = (
    "I confirm a second controlled real broker proof attempt using the validated V3 candidate, "
    "limit order only, count 1, no market orders, no scale, no autonomy, and Dummy must still "
    "pass every gate before any order"
)


class SecondProofAuthorityStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SecondProofAuthority:
    schema_version: int
    authority_id: str
    authority_type: str
    status: SecondProofAuthorityStatus
    prior_proof_registry_hash: str
    prior_proof_status: str
    prior_proof_lock_consumed: bool
    candidate_source: str
    candidate_hash: str
    candidate_market_ticker: str
    candidate_contract_ticker: str
    candidate_price: int
    candidate_count: int
    candidate_order_type: str
    caps_hash: str
    caps_schema_version: int
    caps_authority_epoch: str
    caps_authority_state: str
    caps_authority_registration_sha256: str
    caps_authority_registration_valid: bool
    legacy_caps_authority_invalidated: bool
    execution_authority: bool
    descriptor_hash: str
    runtime_approval_hash: str
    live_submit_required_hash: str | None
    max_attempts: int
    market_orders_allowed: bool
    scale_allowed: bool
    autonomy_allowed: bool
    expires_at: str
    operator_name: str
    reason: str
    exact_typed_confirmation_digest: str
    created_by_operator: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _runtime_approval_hash() -> str | None:
    if not RUNTIME_APPROVALS_DIR.exists():
        return None
    files = sorted(p for p in RUNTIME_APPROVALS_DIR.iterdir() if p.is_file() and p.suffix == ".json")
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest().upper()


def _is_stale(expiry: str) -> bool:
    try:
        dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        return dt < datetime.now(timezone.utc)
    except Exception:
        return True


def _candidate_age_ok(candidate: dict[str, Any], now: datetime) -> bool:
    """True only when the candidate was validated recently enough to trust.

    Market tradability is a point-in-time observation, and every other
    invariant below reads a boolean that was written when that observation was
    made.  Without this check the canonical candidate on the live box --
    validated 2026-07-08 for a market that now returns 404 -- passed every
    gate, because ``market_tradable: True`` was true at the time and nothing
    asked when the time was.

    Fails closed on anything it cannot date: missing, unparseable, timezone
    naive (guessing a zone here could silently widen the window by hours), or
    in the future.
    """
    raw = candidate.get("created_at")
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if created.tzinfo is None:
        return False
    age = (now - created.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= CANDIDATE_MAX_AGE_SECONDS


def _candidate_invariants(
    candidate: dict[str, Any], now: datetime | None = None
) -> tuple[bool, str]:
    """Verify the V3 candidate satisfies the safety preconditions for a second proof."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not candidate.get("candidate_found"):
        return False, "BLOCKED_CANDIDATE_NOT_FOUND"
    if not _candidate_age_ok(candidate, now):
        return False, "BLOCKED_CANDIDATE_STALE"
    if not candidate.get("market_tradable"):
        return False, "BLOCKED_MARKET_NOT_TRADABLE"
    if not candidate.get("contract_tradable"):
        return False, "BLOCKED_CONTRACT_NOT_TRADABLE"
    if not candidate.get("price_validated"):
        return False, "BLOCKED_PRICE_NOT_VALIDATED"
    if candidate.get("order_type") != "LIMIT":
        return False, "BLOCKED_ORDER_TYPE_NOT_LIMIT"
    if candidate.get("count") != 1:
        return False, "BLOCKED_COUNT_NOT_ONE"
    if candidate.get("submit_allowed_now") is not False:
        return False, "BLOCKED_SUBMIT_ALLOWED_UNDER_OLD_AUTHORITY"
    if candidate.get("requires_new_operator_proof_authority") is not True:
        return False, "BLOCKED_NO_NEW_AUTHORITY_REQUIRED"
    return True, ""


def _registry_invariants(registry: dict[str, Any]) -> tuple[bool, str]:
    """Verify the prior real-proof registry shows a consumed first attempt."""
    status = registry.get("latest_real_broker_attempt_status")
    if status not in {"BROKER_REJECTED", "BROKER_ACCEPTED"}:
        return False, "BLOCKED_PRIOR_PROOF_REGISTRY_INVALID"
    if registry.get("latest_real_broker_contacted") is not True:
        return False, "BLOCKED_PRIOR_PROOF_LOCK_NOT_CONSUMED"
    return True, ""


def build_second_proof_authority_draft() -> SecondProofAuthority:
    """Build a draft second-proof authority from the validated V3 candidate.

    Raises ValueError with an exact blocker string if any precondition fails.
    Does not enable live-submit, contact the broker, or consume any lock.
    """
    candidate = _load_json(V3_CANDIDATE_PATH)
    _load_json(V3_REPORT_PATH)
    registry = _load_json(REAL_PROOF_REGISTRY_PATH)

    ok, reason = _candidate_invariants(candidate)
    if not ok:
        raise ValueError(reason)

    ok, reason = _registry_invariants(registry)
    if not ok:
        raise ValueError(reason)

    actual_candidate_hash = _sha256_file(V3_CANDIDATE_PATH)
    caps_authority = evaluate_caps_authority(
        caps_path=CAPS_PATH,
        registration_path=CAPS_AUTHORITY_REGISTRATION_PATH,
    )
    if not caps_authority.config_integrity_valid:
        raise ValueError("BLOCKED_CAPS_V2_CONFIG_INTEGRITY")
    if not caps_authority.authority_registration_valid:
        raise ValueError("BLOCKED_CAPS_AUTHORITY_REGISTRATION_REQUIRED")
    if (
        caps_authority.state
        != "REGISTERED_FOR_SEPARATE_LIVE_GATE_EVALUATION"
    ):
        raise ValueError("BLOCKED_CAPS_AUTHORITY_STATE")
    caps_hash = caps_authority.current_caps_sha256
    registration_hash = caps_authority.authority_registration_sha256
    if not caps_hash or not registration_hash:
        raise ValueError("BLOCKED_CAPS_AUTHORITY_BINDING_MISSING")
    if caps_hash == LEGACY_CAPS_SHA256:
        raise ValueError("BLOCKED_LEGACY_CAPS_AUTHORITY_INVALIDATED")
    descriptor_hash = _sha256_file(ADAPTER_DESCRIPTOR_PATH)
    runtime_approval_hash = _runtime_approval_hash()
    live_submit_hash = _sha256_file(LIVE_SUBMIT_PATH)

    return SecondProofAuthority(
        schema_version=SECOND_PROOF_AUTHORITY_SCHEMA_VERSION,
        authority_id=f"second-proof-{uuid.uuid4().hex[:16]}",
        authority_type="SECOND_CONTROLLED_REAL_BROKER_PROOF",
        status=SecondProofAuthorityStatus.DRAFT,
        prior_proof_registry_hash=_sha256_file(REAL_PROOF_REGISTRY_PATH) or _sha256_text(json.dumps(registry, sort_keys=True)),
        prior_proof_status=registry.get("latest_real_broker_attempt_status", "BROKER_REJECTED"),
        prior_proof_lock_consumed=True,
        candidate_source="V3_READ_ONLY_METADATA_DISCOVERY",
        candidate_hash=actual_candidate_hash or EXPECTED_CANDIDATE_HASH,
        candidate_market_ticker=candidate.get("market_ticker", ""),
        candidate_contract_ticker=candidate.get("contract_ticker", ""),
        candidate_price=int(candidate.get("price", 1)),
        candidate_count=int(candidate.get("count", 1)),
        candidate_order_type=candidate.get("order_type", "LIMIT"),
        caps_hash=caps_hash,
        caps_schema_version=CURRENT_CAPS_SCHEMA_VERSION,
        caps_authority_epoch=CURRENT_CAPS_AUTHORITY_EPOCH,
        caps_authority_state=caps_authority.state,
        caps_authority_registration_sha256=registration_hash,
        caps_authority_registration_valid=True,
        legacy_caps_authority_invalidated=True,
        # A draft records predicates only.  It never carries execution
        # authority, even after operator activation.
        execution_authority=False,
        descriptor_hash=descriptor_hash or EXPECTED_DESCRIPTOR_HASH,
        runtime_approval_hash=runtime_approval_hash or EXPECTED_RUNTIME_APPROVAL_HASH,
        live_submit_required_hash=live_submit_hash or EXPECTED_LIVE_SUBMIT_DISABLED_HASH,
        max_attempts=1,
        market_orders_allowed=False,
        scale_allowed=False,
        autonomy_allowed=False,
        expires_at="",
        operator_name="",
        reason="",
        exact_typed_confirmation_digest="",
        created_by_operator=False,
    )


def activate_second_proof_authority(
    draft: SecondProofAuthority,
    operator_name: str,
    reason: str,
    expires_at: str,
    confirmation: str,
) -> SecondProofAuthority:
    """Activate a draft second-proof authority after exact typed confirmation.

    Raises ValueError with an exact blocker if confirmation mismatch, stale
    hashes, or expired authority.
    """
    if confirmation != REQUIRED_CONFIRMATION:
        raise ValueError("CONFIRMATION_MISMATCH")
    if draft.status != SecondProofAuthorityStatus.DRAFT:
        raise ValueError("AUTHORITY_NOT_DRAFT")
    if not operator_name or not reason or not expires_at:
        raise ValueError("MISSING_OPERATOR_REASON_OR_EXPIRY")
    if _is_stale(expires_at):
        raise ValueError("EXPIRES_AT_STALE")
    if draft.schema_version != SECOND_PROOF_AUTHORITY_SCHEMA_VERSION:
        raise ValueError("AUTHORITY_SCHEMA_VERSION_MISMATCH")
    if draft.caps_hash == LEGACY_CAPS_SHA256:
        raise ValueError("LEGACY_CAPS_AUTHORITY_INVALIDATED")
    if draft.execution_authority is not False:
        raise ValueError("DRAFT_MUST_NOT_CARRY_EXECUTION_AUTHORITY")

    actual_candidate_hash = _sha256_file(V3_CANDIDATE_PATH)
    if actual_candidate_hash != draft.candidate_hash:
        raise ValueError("CANDIDATE_HASH_CHANGED")

    registry = _load_json(REAL_PROOF_REGISTRY_PATH)
    registry_hash = _sha256_file(REAL_PROOF_REGISTRY_PATH) or _sha256_text(json.dumps(registry, sort_keys=True))
    if registry_hash != draft.prior_proof_registry_hash:
        raise ValueError("REGISTRY_HASH_CHANGED")

    inv_ok, inv_reason = _registry_invariants(registry)
    if not inv_ok:
        raise ValueError(inv_reason)

    caps_authority = evaluate_caps_authority(
        caps_path=CAPS_PATH,
        registration_path=CAPS_AUTHORITY_REGISTRATION_PATH,
    )
    if not caps_authority.config_integrity_valid:
        raise ValueError("CAPS_V2_CONFIG_INTEGRITY_INVALID")
    if not caps_authority.authority_registration_valid:
        raise ValueError("CAPS_AUTHORITY_REGISTRATION_INVALID")
    if caps_authority.current_caps_sha256 != draft.caps_hash:
        raise ValueError("CAPS_HASH_CHANGED")
    if caps_authority.schema_version != draft.caps_schema_version:
        raise ValueError("CAPS_SCHEMA_VERSION_CHANGED")
    if caps_authority.authority_epoch != draft.caps_authority_epoch:
        raise ValueError("CAPS_AUTHORITY_EPOCH_CHANGED")
    if (
        caps_authority.authority_registration_sha256
        != draft.caps_authority_registration_sha256
    ):
        raise ValueError("CAPS_AUTHORITY_REGISTRATION_CHANGED")

    live_submit_hash = _sha256_file(LIVE_SUBMIT_PATH)

    return SecondProofAuthority(
        **{
            **asdict(draft),
            "status": SecondProofAuthorityStatus.ACTIVE,
            "operator_name": operator_name,
            "reason": reason,
            "expires_at": expires_at,
            "exact_typed_confirmation_digest": _sha256_text(confirmation),
            "created_by_operator": True,
            "live_submit_required_hash": live_submit_hash or EXPECTED_LIVE_SUBMIT_DISABLED_HASH,
        }
    )


def mark_authority_used(authority: SecondProofAuthority) -> SecondProofAuthority:
    """Transition an active authority to used after the single allowed attempt."""
    return SecondProofAuthority(**{**asdict(authority), "status": SecondProofAuthorityStatus.USED})


def authority_to_dict(authority: SecondProofAuthority) -> dict[str, Any]:
    """Serialize authority to a JSON-safe dict."""
    data = asdict(authority)
    data["status"] = authority.status.value
    return data


def authority_from_dict(data: dict[str, Any]) -> SecondProofAuthority:
    """Deserialize authority from a JSON-safe dict."""
    if data.get("schema_version") != SECOND_PROOF_AUTHORITY_SCHEMA_VERSION:
        raise ValueError("AUTHORITY_SCHEMA_VERSION_MISMATCH")
    if data.get("caps_schema_version") != CURRENT_CAPS_SCHEMA_VERSION:
        raise ValueError("CAPS_SCHEMA_VERSION_MISMATCH")
    if data.get("caps_authority_epoch") != CURRENT_CAPS_AUTHORITY_EPOCH:
        raise ValueError("CAPS_AUTHORITY_EPOCH_MISMATCH")
    if data.get("caps_hash") in {None, "", LEGACY_CAPS_SHA256}:
        raise ValueError("LEGACY_OR_MISSING_CAPS_HASH")
    if data.get("caps_authority_registration_valid") is not True:
        raise ValueError("CAPS_AUTHORITY_REGISTRATION_NOT_VALID")
    if data.get("execution_authority") is not False:
        raise ValueError("AUTHORITY_MUST_NOT_CARRY_EXECUTION_AUTHORITY")
    status_value = data.get("status")
    if not isinstance(status_value, str):
        raise ValueError("AUTHORITY_STATUS_MISSING")
    status = SecondProofAuthorityStatus(status_value)
    fields = {k: v for k, v in data.items() if k != "status"}
    return SecondProofAuthority(status=status, **fields)


def authority_status(authority: SecondProofAuthority | None) -> dict[str, Any]:
    """Return a secret-free status summary."""
    if authority is None:
        return {"status": "absent"}
    return {
        "status": authority.status.value,
        "authority_id": authority.authority_id,
        "candidate_market_ticker": authority.candidate_market_ticker,
        "candidate_contract_ticker": authority.candidate_contract_ticker,
        "candidate_price": authority.candidate_price,
        "candidate_count": authority.candidate_count,
        "candidate_order_type": authority.candidate_order_type,
        "candidate_hash": authority.candidate_hash,
        "schema_version": authority.schema_version,
        "caps_schema_version": authority.caps_schema_version,
        "caps_authority_epoch": authority.caps_authority_epoch,
        "caps_authority_state": authority.caps_authority_state,
        "caps_authority_registration_valid": authority.caps_authority_registration_valid,
        "legacy_caps_authority_invalidated": authority.legacy_caps_authority_invalidated,
        "execution_authority": authority.execution_authority,
        "market_orders_allowed": authority.market_orders_allowed,
        "scale_allowed": authority.scale_allowed,
        "autonomy_allowed": authority.autonomy_allowed,
    }
