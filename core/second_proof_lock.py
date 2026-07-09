"""Fresh second-proof lock namespace.

Tracks whether the single allowed second real-broker attempt has already been
consumed. This is independent of the first-proof registry in
`artifacts/dummy/real_proof_registry.json`; it must never erase or reset that
prior evidence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECOND_PROOF_LOCK_DIR = Path("runtime/proof_locks")


def second_proof_lock_path(authority_id: str) -> Path:
    """Return the safe lock file path for an authority id."""
    safe_id = Path(authority_id).name
    return SECOND_PROOF_LOCK_DIR / f"second_proof_{safe_id}.json"


def load_second_proof_lock(authority_id: str) -> dict[str, Any] | None:
    """Read the lock file for an authority id, or None if absent/invalid."""
    path = second_proof_lock_path(authority_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def is_second_proof_lock_consumed(authority_id: str) -> bool:
    """Return True if the second-proof lock for this authority is consumed."""
    data = load_second_proof_lock(authority_id)
    if data is None:
        return False
    return bool(data.get("consumed"))


def any_second_proof_attempt_consumed() -> bool:
    """Return True if any second-proof lock file is marked consumed."""
    if not SECOND_PROOF_LOCK_DIR.exists():
        return False
    for path in SECOND_PROOF_LOCK_DIR.iterdir():
        if not path.is_file() or not path.name.startswith("second_proof_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("consumed") is True:
            return True
    return False


def consume_second_proof_lock(
    authority_id: str,
    result: dict[str, Any],
) -> Path:
    """Mark the second-proof lock consumed and preserve the attempt result.

    Returns the lock file path. Does not mutate the first-proof registry.
    """
    path = second_proof_lock_path(authority_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_result: dict[str, Any] = {
        "broker_contacted": bool(result.get("broker_contacted")),
        "accepted": bool(result.get("accepted")),
        "rejected": bool(result.get("rejected")),
        "reason": str(result.get("reason", "")),
        "broker_order_id": str(result.get("broker_order_id", "")) if result.get("broker_order_id") else "",
        "broker_rejection_code": str(result.get("broker_rejection_code", "")) if result.get("broker_rejection_code") else "",
    }
    payload = {
        "authority_id": authority_id,
        "consumed": True,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        **safe_result,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def create_second_proof_lock(authority_id: str) -> Path:
    """Create a fresh unconsumed second-proof lock namespace for an authority."""
    path = second_proof_lock_path(authority_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "authority_id": authority_id,
        "consumed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
