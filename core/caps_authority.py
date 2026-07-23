"""Fail-closed authority boundary for versioned live risk caps.

Changing ``configs/caps.json`` invalidates every approval that was bound to the
previous raw file hash.  Code may register a new *protected* baseline, but it
must never manufacture the separate operator registration needed to use that
baseline in a live-authority decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAPS_PATH = ROOT / "configs" / "caps.json"
CAPS_AUTHORITY_REGISTRATION_PATH = (
    ROOT / "runtime" / "operator_external" / "caps_authority_registration_v2.json"
)

CURRENT_CAPS_SCHEMA_VERSION = 2
CURRENT_CAPS_AUTHORITY_EPOCH = "caps-v2-kalshi-category-metadata-20260722"
# Re-sealed 2026-07-22 (same epoch, same JSON data): the original seal was
# computed on pre-commit working-tree bytes that a local normalizer/eol pass
# rewrote before the wave was committed, so it matched no version-controlled
# artifact. This hash pins the canonical committed LF bytes of
# configs/caps.json; .gitattributes marks configs/*.json -text so a checkout
# can never rewrite the sealed bytes again. No operator registration was
# active at re-seal time, and registration remains required + invalid until
# an operator issues one against exactly this hash.
PROTECTED_CAPS_SHA256 = "62878A5F062D71D2EA3EFC3D998874B887FD8D8E885C7745231208F03D913797"
LEGACY_CAPS_SHA256 = "F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5"
UNVERSIONED_MIGRATION_SHA256 = "498256CC426B29905412614DE941F924FF903C166AF2CD99ED092B2B8DB78492"
REQUIRED_REGISTRATION_SCOPE = "caps_policy_registration_for_controlled_firewall_only"
REQUIRED_REGISTRATION_ACK = (
    "I approve this exact caps-v2 hash for controlled firewall-only proof use, "
    "with no market orders, no scale, no autonomy, and every other live gate still required"
)


@dataclass(frozen=True)
class CapsAuthorityStatus:
    state: str
    current_caps_sha256: str | None
    protected_caps_sha256: str
    schema_version: int | None
    authority_epoch: str | None
    config_integrity_valid: bool
    authority_registration_required: bool
    authority_registration_present: bool
    authority_registration_valid: bool
    authority_registration_sha256: str | None
    legacy_authority_invalidated: bool
    errors: tuple[str, ...]
    execution_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["errors"] = list(self.errors)
        return data


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except OSError:
        return None


def _load_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable:{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, "not_an_object"
    return value, None


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_caps_authority(
    *,
    caps_path: Path = CAPS_PATH,
    registration_path: Path = CAPS_AUTHORITY_REGISTRATION_PATH,
    now: datetime | None = None,
) -> CapsAuthorityStatus:
    """Read and validate caps plus a separately authored operator registration.

    This function is deliberately read-only.  Matching the protected code
    baseline proves configuration integrity only; it does not carry forward
    any approval from the legacy caps hash.
    """

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    errors: list[str] = []
    caps_hash = _sha256(caps_path)
    caps, caps_error = _load_object(caps_path)
    schema_version = caps.get("schema_version") if caps else None
    authority_epoch = caps.get("authority_epoch") if caps else None
    registration_required = (
        caps.get("authority_registration_required") is True if caps else True
    )

    if caps_error:
        errors.append(f"CAPS_CONFIG_{caps_error.upper()}")
    if caps_hash != PROTECTED_CAPS_SHA256:
        errors.append("CAPS_PROTECTED_HASH_MISMATCH")
    if schema_version != CURRENT_CAPS_SCHEMA_VERSION:
        errors.append("CAPS_SCHEMA_VERSION_MISMATCH")
    if authority_epoch != CURRENT_CAPS_AUTHORITY_EPOCH:
        errors.append("CAPS_AUTHORITY_EPOCH_MISMATCH")
    if not registration_required:
        errors.append("CAPS_AUTHORITY_REGISTRATION_NOT_REQUIRED")

    config_valid = not errors
    registration, registration_error = _load_object(registration_path)
    registration_present = registration_error != "missing"
    registration_hash = _sha256(registration_path)
    registration_errors: list[str] = []
    if registration_error:
        registration_errors.append(
            "CAPS_AUTHORITY_REGISTRATION_MISSING"
            if registration_error == "missing"
            else "CAPS_AUTHORITY_REGISTRATION_UNREADABLE"
        )
    else:
        assert registration is not None
        expected = {
            "schema_version": 1,
            "caps_config_schema_version": CURRENT_CAPS_SCHEMA_VERSION,
            "authority_epoch": CURRENT_CAPS_AUTHORITY_EPOCH,
            "caps_sha256": PROTECTED_CAPS_SHA256,
            "scope": REQUIRED_REGISTRATION_SCOPE,
            "exact_acknowledgement": REQUIRED_REGISTRATION_ACK,
            "not_self_authorized_by_dummy": True,
            "live_submit_enabled_by_registration": False,
            "market_orders_allowed": False,
            "scale_allowed": False,
            "autonomy_allowed": False,
        }
        for key, value in expected.items():
            if registration.get(key) != value:
                registration_errors.append(f"CAPS_AUTHORITY_REGISTRATION_{key.upper()}_MISMATCH")
        for key in ("operator", "reason"):
            if not isinstance(registration.get(key), str) or not registration[key].strip():
                registration_errors.append(f"CAPS_AUTHORITY_REGISTRATION_{key.upper()}_MISSING")
        issued_at = _parse_utc(registration.get("issued_at"))
        expires_at = _parse_utc(registration.get("expires_at"))
        if issued_at is None or issued_at > now:
            registration_errors.append("CAPS_AUTHORITY_REGISTRATION_ISSUED_AT_INVALID")
        if expires_at is None or expires_at <= now:
            registration_errors.append("CAPS_AUTHORITY_REGISTRATION_EXPIRED")

    registration_valid = config_valid and not registration_errors
    all_errors = tuple(errors + registration_errors)
    if not config_valid:
        state = "CONFIG_INTEGRITY_BLOCKED"
    elif not registration_valid:
        state = "REVIEW_REQUIRED"
    else:
        state = "REGISTERED_FOR_SEPARATE_LIVE_GATE_EVALUATION"

    return CapsAuthorityStatus(
        state=state,
        current_caps_sha256=caps_hash,
        protected_caps_sha256=PROTECTED_CAPS_SHA256,
        schema_version=(schema_version if type(schema_version) is int else None),
        authority_epoch=(authority_epoch if isinstance(authority_epoch, str) else None),
        config_integrity_valid=config_valid,
        authority_registration_required=True,
        authority_registration_present=registration_present,
        authority_registration_valid=registration_valid,
        authority_registration_sha256=registration_hash,
        legacy_authority_invalidated=True,
        errors=all_errors,
        # A caps registration is only one predicate.  It never grants live
        # execution authority by itself.
        execution_authority=False,
    )


__all__ = [
    "CAPS_AUTHORITY_REGISTRATION_PATH",
    "CURRENT_CAPS_AUTHORITY_EPOCH",
    "CURRENT_CAPS_SCHEMA_VERSION",
    "LEGACY_CAPS_SHA256",
    "PROTECTED_CAPS_SHA256",
    "REQUIRED_REGISTRATION_ACK",
    "REQUIRED_REGISTRATION_SCOPE",
    "CapsAuthorityStatus",
    "evaluate_caps_authority",
]
