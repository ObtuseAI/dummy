"""Exhaustive fail-closed matrix for the shared live-execution classifier."""

from __future__ import annotations

from copy import deepcopy

import pytest

from core.live_execution_mode import (
    LIVE_PROOF_ENV_ACK,
    LiveExecutionMode,
    classify_live_execution_mode,
)
from core.live_submit_state import LIVE_SUBMIT_REQUIRED_ACK, build_caps_authority_binding
from tests.caps_authority_test_helpers import registered_caps_status


CAPS_AUTHORITY = registered_caps_status()


def _enabled_config() -> dict[str, object]:
    return {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "fixture-operator",
        "reason": "offline authority classifier matrix",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
        "scale_enabled": False,
        "autonomy_enabled": False,
        **build_caps_authority_binding(CAPS_AUTHORITY),
    }


def _ready_context() -> dict[str, object]:
    return {
        "live_submit_config": _enabled_config(),
        "env": {
            "DUMMY_LIVE_PROOF_MODE": "1",
            "DUMMY_LIVE_PROOF_ACK": LIVE_PROOF_ENV_ACK,
            "UNRELATED_SECRET": "must-not-escape",
        },
        "seal_status": "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT",
        "caps_strict": True,
        "descriptor_staged": True,
        "credentials_ready": True,
        "proof_lock_clear": True,
        "caps_authority_status": CAPS_AUTHORITY,
    }


@pytest.mark.parametrize(
    ("field", "blocked_value", "expected_blocker"),
    [
        ("env_mode", False, "ENV_GATE_MISSING"),
        ("env_ack", False, "ENV_GATE_MISSING"),
        ("seal_status", "BLOCKED", "COMMAND_SEAL_NOT_READY"),
        ("caps_strict", False, "CAPS_NOT_STRICT"),
        ("descriptor_staged", False, "ADAPTER_DESCRIPTOR_NOT_STAGED"),
        ("credentials_ready", False, "CREDENTIALS_NOT_READY"),
        ("proof_lock_clear", False, "PROOF_LOCK_USED"),
    ],
)
def test_every_runtime_predicate_blocks_independently(
    field: str,
    blocked_value: object,
    expected_blocker: str,
) -> None:
    context = _ready_context()
    if field == "env_mode":
        context["env"] = {
            **context["env"],  # type: ignore[arg-type]
            "DUMMY_LIVE_PROOF_MODE": "0",
        }
    elif field == "env_ack":
        context["env"] = {
            **context["env"],  # type: ignore[arg-type]
            "DUMMY_LIVE_PROOF_ACK": "wrong",
        }
    else:
        context[field] = blocked_value

    mode, blocker, observed = classify_live_execution_mode(**context)  # type: ignore[arg-type]

    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == expected_blocker
    assert "UNRELATED_SECRET" not in observed
    assert "must-not-escape" not in repr(observed)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("proof_scope", "unbounded"),
        ("auto_run", True),
        ("weaken_gates", True),
        ("requires_command_seal", False),
        ("requires_livebrokerfirewall", False),
        ("requires_limit_order", False),
        ("market_orders_allowed", True),
        ("order_type_policy", "MARKET"),
        ("max_order_count", 2),
        ("expiry", "2020-01-01T00:00:00Z"),
        ("explicit_acknowledgement", "wrong"),
        ("scale_enabled", True),
        ("autonomy_enabled", True),
        ("caps_hashes", ["WRONG"]),
    ],
)
def test_every_live_submit_safety_field_fails_closed(
    field: str,
    invalid_value: object,
) -> None:
    context = _ready_context()
    config = deepcopy(context["live_submit_config"])
    assert isinstance(config, dict)
    config[field] = invalid_value
    context["live_submit_config"] = config

    mode, blocker, observed = classify_live_execution_mode(**context)  # type: ignore[arg-type]

    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == "LIVE_SUBMIT_INVALID"
    assert observed["errors"]


def test_default_disabled_cannot_be_upgraded_by_all_other_positive_gates() -> None:
    context = _ready_context()
    context["live_submit_config"] = {"enabled": False}

    mode, blocker, _ = classify_live_execution_mode(**context)  # type: ignore[arg-type]

    assert mode is LiveExecutionMode.DEFAULT_DISABLED
    assert blocker == "DEFAULT_DISABLED"


def test_caps_registration_is_necessary_but_never_self_grants_authority() -> None:
    context = _ready_context()
    blocked_caps = {
        **CAPS_AUTHORITY.to_dict(),
        "state": "REVIEW_REQUIRED",
        "authority_registration_present": False,
        "authority_registration_valid": False,
        "authority_registration_sha256": None,
    }
    context["caps_authority_status"] = blocked_caps

    mode, blocker, observed = classify_live_execution_mode(**context)  # type: ignore[arg-type]

    assert CAPS_AUTHORITY.execution_authority is False
    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == "LIVE_SUBMIT_INVALID"
    assert any("registration" in error for error in observed["errors"])
