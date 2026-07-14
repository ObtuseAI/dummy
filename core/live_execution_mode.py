"""Shared live execution mode classifier for the Dummy repo.

Distinguishes four explicit execution modes so that callers can decide whether
a live broker submit is allowed, rehearsed, blocked, or default-disabled.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from core.live_submit_state import (
    validate_default_disabled,
    validate_operator_one_proof_enabled,
)

# Env-gate acknowledgement required for one-shot-live commands.
# This is distinct from the configs/live_submit.json explicit_acknowledgement.
LIVE_PROOF_ENV_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class LiveExecutionMode(Enum):
    DEFAULT_DISABLED = "default_disabled"
    REHEARSAL_OR_TEST_DOUBLE = "rehearsal_or_test_double"
    OPERATOR_ONE_PROOF_LIVE_READY = "operator_one_proof_live_ready"
    INVALID_OR_BLOCKED = "invalid_or_blocked"


def classify_live_execution_mode(
    live_submit_config: dict[str, Any],
    env: dict[str, str],
    seal_status: str,
    caps_strict: bool,
    descriptor_staged: bool,
    credentials_ready: bool,
    proof_lock_clear: bool,
    authority_context: dict[str, Any] | None = None,
) -> tuple[LiveExecutionMode, str, dict[str, Any]]:
    """Classify the current live execution environment.

    Returns (mode, blocker, context). blocker is empty when mode is
    OPERATOR_ONE_PROOF_LIVE_READY. context contains the predicates that were
    evaluated; it never contains secret values.
    """
    context: dict[str, Any] = {
        "live_submit_config": live_submit_config,
        "env_mode": env.get("DUMMY_LIVE_PROOF_MODE") == "1",
        "env_ack": env.get("DUMMY_LIVE_PROOF_ACK") == LIVE_PROOF_ENV_ACK,
        "seal_status": seal_status,
        "caps_strict": caps_strict,
        "descriptor_staged": descriptor_staged,
        "credentials_ready": credentials_ready,
        "proof_lock_clear": proof_lock_clear,
    }

    disabled = validate_default_disabled(live_submit_config)
    if disabled.ok:
        return LiveExecutionMode.DEFAULT_DISABLED, "DEFAULT_DISABLED", context

    enabled = validate_operator_one_proof_enabled(
        live_submit_config, authority_context=authority_context
    )
    if not enabled.ok:
        return (
            LiveExecutionMode.INVALID_OR_BLOCKED,
            "LIVE_SUBMIT_INVALID",
            {**context, "errors": enabled.errors},
        )

    if not context["env_mode"] or not context["env_ack"]:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "ENV_GATE_MISSING", context

    if seal_status != "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT":
        return LiveExecutionMode.INVALID_OR_BLOCKED, "COMMAND_SEAL_NOT_READY", context

    if not caps_strict:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CAPS_NOT_STRICT", context

    if not descriptor_staged:
        return (
            LiveExecutionMode.INVALID_OR_BLOCKED,
            "ADAPTER_DESCRIPTOR_NOT_STAGED",
            context,
        )

    if not credentials_ready:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CREDENTIALS_NOT_READY", context

    if not proof_lock_clear:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "PROOF_LOCK_USED", context

    return LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY, "", context
