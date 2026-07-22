"""Shared live-submit state model for the Dummy repo.

This module distinguishes two valid states:

* DEFAULT_DISABLED_VALID  — live-submit is disabled; no live proof can run.
* OPERATOR_ONE_PROOF_ENABLED_VALID — live-submit is enabled for exactly one
  controlled, operator-approved, expiring, command-sealed, LiveBrokerFirewall-routed,
  limit-only proof.

Anything else is INVALID. The model is used by the firewall, the operator-control
backend, the authority appliance, and tests so that safety invariants are expressed
in one place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from core.caps_authority import (
    CURRENT_CAPS_AUTHORITY_EPOCH,
    CURRENT_CAPS_SCHEMA_VERSION,
    CapsAuthorityStatus,
    evaluate_caps_authority,
)

# This is the acknowledgement the firewall itself requires in
# configs/live_submit.json before it will treat live-submit as enabled.
LIVE_SUBMIT_REQUIRED_ACK = (
    "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only"
)

# This is the typed confirmation an operator must supply to the dashboard/appliance
# write endpoint before configs/live_submit.json may be modified.
LIVE_SUBMIT_TYPED_CONFIRMATION = (
    "I confirm live-submit is enabled for one controlled proof only and Dummy must "
    "still pass all gates before any order"
)


class LiveSubmitState(Enum):
    DEFAULT_DISABLED_VALID = "default_disabled_valid"
    OPERATOR_ONE_PROOF_ENABLED_VALID = "operator_one_proof_enabled_valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    state: LiveSubmitState
    errors: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


def _caps_status_value(
    status: CapsAuthorityStatus | dict[str, Any], key: str
) -> Any:
    if isinstance(status, dict):
        return status.get(key)
    return getattr(status, key)


def build_caps_authority_binding(
    status: CapsAuthorityStatus | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the non-secret caps-v2 fields an enabled config must bind.

    Copying these fields does not grant authority.  The enabled-state validator
    independently re-evaluates the current caps file and external registration
    before accepting the binding.
    """

    status = status or evaluate_caps_authority()
    caps_hash = _caps_status_value(status, "current_caps_sha256")
    return {
        "caps_schema_version": _caps_status_value(status, "schema_version"),
        "caps_authority_epoch": _caps_status_value(status, "authority_epoch"),
        "caps_authority_registration_required": True,
        "caps_authority_registration_sha256": _caps_status_value(
            status, "authority_registration_sha256"
        ),
        "caps_hashes": [caps_hash] if isinstance(caps_hash, str) and caps_hash else [],
    }


def _is_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _is_stale(expiry: str) -> bool:
    try:
        dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        return dt < datetime.now(timezone.utc)
    except Exception:
        return True


def load_live_submit_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load configs/live_submit.json, returning a safe default if absent/invalid."""
    if path is None:
        path = Path("configs/live_submit.json")
    else:
        path = Path(path)
    if not path.exists():
        return {"enabled": False, "note": "config absent"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "note": "invalid JSON"}
    if not isinstance(data, dict):
        return {"enabled": False, "note": "not a JSON object"}
    return data


def classify_live_submit_state(
    config: dict[str, Any] | None = None,
    *,
    caps_authority_status: CapsAuthorityStatus | dict[str, Any] | None = None,
) -> LiveSubmitState:
    """Return the coarse state classification for a live-submit config."""
    if config is None:
        config = load_live_submit_config()
    result = validate_operator_one_proof_enabled(
        config, caps_authority_status=caps_authority_status
    )
    if result.ok:
        return LiveSubmitState.OPERATOR_ONE_PROOF_ENABLED_VALID
    result = validate_default_disabled(config)
    if result.ok:
        return LiveSubmitState.DEFAULT_DISABLED_VALID
    return LiveSubmitState.INVALID


def validate_default_disabled(config: dict[str, Any] | None = None) -> ValidationResult:
    """Validate the default safe state: enabled must be explicitly false."""
    if config is None:
        config = load_live_submit_config()
    enabled = config.get("enabled")
    if enabled is not False and enabled is not None:
        return ValidationResult(
            ok=False,
            state=LiveSubmitState.INVALID,
            errors=["enabled is not false; default disabled state requires enabled=false"],
            config=config,
        )
    return ValidationResult(ok=True, state=LiveSubmitState.DEFAULT_DISABLED_VALID, config=config)


def validate_operator_one_proof_enabled(
    config: dict[str, Any] | None = None,
    *,
    authority_context: dict[str, Any] | None = None,
    caps_authority_status: CapsAuthorityStatus | dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate the explicit operator-approved one-proof enabled state.

    The config must be a dict with every safety predicate set exactly right.
    If authority_context is supplied, it is checked for a runtime approval whose
    scope matches the controlled production pilot scope.
    """
    if config is None:
        config = load_live_submit_config()
    errors: list[str] = []

    if not isinstance(config, dict):
        return ValidationResult(
            ok=False,
            state=LiveSubmitState.INVALID,
            errors=["config must be a JSON object"],
            config=config,
        )

    if config.get("enabled") is not True:
        errors.append("enabled must be true")

    if config.get("proof_scope") != "one_controlled_proof":
        errors.append("proof_scope must be 'one_controlled_proof'")

    if config.get("auto_run") is not False:
        errors.append("auto_run must be false")

    if config.get("weaken_gates") is not False:
        errors.append("weaken_gates must be false")

    if config.get("requires_command_seal") is not True:
        errors.append("requires_command_seal must be true")

    if config.get("requires_livebrokerfirewall") is not True:
        errors.append("requires_livebrokerfirewall must be true")

    if config.get("requires_limit_order") is not True:
        errors.append("requires_limit_order must be true")

    if config.get("market_orders_allowed") is not False:
        errors.append("market_orders_allowed must be false")

    order_type_policy = config.get("order_type_policy")
    if order_type_policy is not None and order_type_policy != "LIMIT_ONLY":
        errors.append("order_type_policy must be 'LIMIT_ONLY' if present")

    max_order_count = config.get("max_order_count")
    if max_order_count is not None and (not isinstance(max_order_count, int) or max_order_count > 1 or max_order_count < 1):
        errors.append("max_order_count must be 1 if present")

    expiry = config.get("expiry")
    if not isinstance(expiry, str) or not _is_iso_timestamp(expiry):
        errors.append("expiry must be a valid ISO-8601 timestamp")
    elif _is_stale(expiry):
        errors.append("expiry is stale")

    for key in ("operator", "reason", "timestamp"):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")

    if config.get("explicit_acknowledgement") != LIVE_SUBMIT_REQUIRED_ACK:
        errors.append("explicit_acknowledgement does not match the required LiveBrokerFirewall ack")

    # Scale / autonomy must be absent or explicitly disabled.
    if config.get("scale_enabled") is True:
        errors.append("scale must not be enabled")
    if config.get("autonomy_enabled") is True:
        errors.append("autonomy must not be enabled")

    # Optional descriptor hashes are shape-checked.  Caps hashes are mandatory
    # and exact under caps schema v2; a legacy hash can never carry authority
    # forward into an enabled live-submit config.
    for list_key in ("descriptor_hashes",):
        value = config.get(list_key)
        if value is not None and not isinstance(value, list):
            errors.append(f"{list_key} must be a list if present")

    caps_status = caps_authority_status or evaluate_caps_authority()
    config_integrity_valid = _caps_status_value(
        caps_status, "config_integrity_valid"
    )
    registration_valid = _caps_status_value(
        caps_status, "authority_registration_valid"
    )
    authority_state = _caps_status_value(caps_status, "state")
    current_caps_hash = _caps_status_value(caps_status, "current_caps_sha256")
    registration_hash = _caps_status_value(
        caps_status, "authority_registration_sha256"
    )

    if config_integrity_valid is not True:
        errors.append("current caps-v2 configuration integrity is not valid")
    if registration_valid is not True:
        errors.append("fresh caps-v2 authority registration is not valid")
    if authority_state != "REGISTERED_FOR_SEPARATE_LIVE_GATE_EVALUATION":
        errors.append("caps-v2 authority is not registered for separate live-gate evaluation")
    if config.get("caps_schema_version") != CURRENT_CAPS_SCHEMA_VERSION:
        errors.append(
            f"caps_schema_version must be {CURRENT_CAPS_SCHEMA_VERSION}"
        )
    if config.get("caps_authority_epoch") != CURRENT_CAPS_AUTHORITY_EPOCH:
        errors.append("caps_authority_epoch does not match the current protected epoch")
    if config.get("caps_authority_registration_required") is not True:
        errors.append("caps_authority_registration_required must be true")
    if not isinstance(current_caps_hash, str) or config.get("caps_hashes") != [
        current_caps_hash
    ]:
        errors.append("caps_hashes must bind exactly the current protected caps-v2 hash")
    if (
        not isinstance(registration_hash, str)
        or not registration_hash
        or config.get("caps_authority_registration_sha256") != registration_hash
    ):
        errors.append(
            "caps_authority_registration_sha256 must bind the current valid registration"
        )

    # Runtime approval check when authority context is supplied.
    if authority_context is not None:
        approval = authority_context.get("approval") or {}
        if not approval:
            errors.append("runtime approval missing in authority_context")
        elif approval.get("scope") != "one_controlled_production_pilot_via_firewall_only":
            errors.append("runtime approval scope mismatch")
        elif not _is_iso_timestamp(approval.get("expiration", "")):
            errors.append("runtime approval has no valid expiry")
        elif _is_stale(approval.get("expiration", "")):
            errors.append("runtime approval is expired")

    ok = not errors
    return ValidationResult(
        ok=ok,
        state=LiveSubmitState.OPERATOR_ONE_PROOF_ENABLED_VALID if ok else LiveSubmitState.INVALID,
        errors=errors,
        config=config,
    )


def is_live_submit_armed(
    config: dict[str, Any] | None = None,
    *,
    caps_authority_status: CapsAuthorityStatus | dict[str, Any] | None = None,
) -> bool:
    """Return True only when the config is in the valid operator-one-proof enabled state."""
    return validate_operator_one_proof_enabled(
        config, caps_authority_status=caps_authority_status
    ).ok


__all__ = [
    "LIVE_SUBMIT_REQUIRED_ACK",
    "LIVE_SUBMIT_TYPED_CONFIRMATION",
    "LiveSubmitState",
    "ValidationResult",
    "build_caps_authority_binding",
    "classify_live_submit_state",
    "is_live_submit_armed",
    "load_live_submit_config",
    "validate_default_disabled",
    "validate_operator_one_proof_enabled",
]
