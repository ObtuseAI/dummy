"""Read-only operator status views promoted out of milestone snapshots.

These helpers only read already-produced artifacts.  They cannot write
authority files, contact a broker, submit/cancel orders, or grant execution
authority.  Historical ``v207``, ``v208`` and ``v213`` report factories remain
archived for compatibility, while current runners use this stable module.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc

AUTHORITY_STATES = (
    "DRY_LOCKED",
    "LIVE_BLOCKED_AUTHORITY_ABSENT",
    "LIVE_READONLY_ALLOWED",
    "LIVE_PROOF_ARMABLE",
    "LIVE_PROOF_ALREADY_LOCKED",
)

NEXT_OPERATOR_ACTIONS = (
    "PROVIDE_EXACT_APPROVAL_FILES",
    "ENABLE_LIVE_SUBMIT_OPERATOR_SIDE",
    "CONFIRM_CAPS_CONFIG",
    "INJECT_LIVEBROKERFIREWALL_ADAPTER",
    "OPTIONALLY_PROVIDE_BROKER_READONLY_APPROVAL",
    "RUN_FIRST_LIVE_PROOF_WITH_CLI_ENV_GATE",
)


def build_activation_snapshot() -> dict[str, Any]:
    """Return the legacy activation inputs as an explicitly read-only view."""

    return {
        "authority_status": str(
            sgc.load_artifact("final_report_v195.json").get(
                "activation_binder_controller_status",
                "PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE",
            )
        ),
        "live_proof_status": str(
            sgc.load_artifact("final_report_v199.json").get(
                "first_live_proof_gate_controller_status",
                "PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED",
            )
        ),
        "reconcile_status": str(
            sgc.load_artifact("final_report_v200.json").get(
                "reconcile_controller_status",
                "PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE",
            )
        ),
        "forensic_status": str(
            sgc.load_artifact("final_report_v201.json").get(
                "forensic_controller_status",
                "PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW",
            )
        ),
        "scale_status": str(
            sgc.load_artifact("final_report_v202.json").get(
                "scale_recommendation", "SCALE_BLOCKED_NO_LIVE_PROOF"
            )
        ),
        "autonomy_status": str(
            sgc.load_artifact("final_report_v202.json").get(
                "autonomy_recommendation", "AUTONOMY_BLOCKED_NO_LIVE_PROOF"
            )
        ),
        "completion_percentages": sgc.load_artifact("final_report_v205.json").get(
            "completion_percentages", {}
        ),
        "canonical_blockers": sgc.load_artifact("final_report_v205.json").get(
            "canonical_blocker_list", []
        ),
        "next_operator_actions": list(NEXT_OPERATOR_ACTIONS),
        "safe_mode": "READ_ONLY_FAIL_CLOSED",
        "ui_submit_enabled": False,
        "ui_config_write_enabled": False,
        "total_live_orders": 0,
        "broker_contacted": False,
        "approval_files_written": 0,
    }


def resolve_authority(
    *,
    approval_ok_override: bool | None = None,
    config_ok_override: bool | None = None,
    firewall_ok_override: bool | None = None,
    broker_readonly_ok_override: bool | None = None,
    proof_already_locked_override: bool | None = None,
) -> dict[str, Any]:
    """Resolve status without mutating or independently validating authority.

    The optional overrides are retained for deterministic contract tests.  No
    result from this read-only status helper is sufficient execution authority.
    """

    baseline = sgc.baseline_status("final_report_v207.json", "V207")
    approval_ok = (
        bool(approval_ok_override)
        if approval_ok_override is not None
        else str(
            sgc.load_artifact("final_report_v206.json").get(
                "activation_manifest_controller_status", ""
            )
        )
        == "PASS_ACTIVATION_MANIFEST_LINTED_VALID"
    )
    config_ok = (
        bool(config_ok_override)
        if config_ok_override is not None
        else str(
            sgc.load_artifact("final_report_v196.json").get(
                "config_quorum_controller_status", ""
            )
        )
        == "PASS_LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE"
    )
    firewall_ok = (
        bool(firewall_ok_override)
        if firewall_ok_override is not None
        else str(
            sgc.load_artifact("final_report_v197.json").get(
                "firewall_broker_controller_status", ""
            )
        )
        == "PASS_FIREWALL_AND_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
    )
    broker_readonly_ok = (
        bool(broker_readonly_ok_override)
        if broker_readonly_ok_override is not None
        else False
    )
    proof_already_locked = (
        bool(proof_already_locked_override)
        if proof_already_locked_override is not None
        else str(
            sgc.load_artifact("final_report_v199.json").get(
                "first_live_proof_gate_controller_status", ""
            )
        )
        == "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED"
    )

    if proof_already_locked:
        authority_state = "LIVE_PROOF_ALREADY_LOCKED"
    elif approval_ok and config_ok and firewall_ok:
        authority_state = "LIVE_PROOF_ARMABLE"
    elif broker_readonly_ok:
        authority_state = "LIVE_READONLY_ALLOWED"
    elif approval_ok or config_ok or firewall_ok:
        authority_state = "LIVE_BLOCKED_AUTHORITY_ABSENT"
    else:
        authority_state = "DRY_LOCKED"

    armable = authority_state == "LIVE_PROOF_ARMABLE"
    if baseline.startswith("FAIL"):
        controller_status = "FAIL_AUTHORITY_RESOLVER_BASELINE_REGRESSION"
        blockers = ["FAIL_V207_BASELINE_REGRESSION"]
    elif armable:
        controller_status = "PASS_AUTHORITY_RESOLVER_LIVE_PROOF_ARMABLE_NO_SUBMIT"
        blockers = []
    else:
        controller_status = "PARTIAL_AUTHORITY_RESOLVER_NOT_ARMABLE"
        blockers = []
        if not approval_ok:
            blockers.append("EXACT_APPROVAL_ABSENT")
        if not config_ok:
            blockers.append("CONFIG_CAPS_QUORUM_ABSENT")
        if not firewall_ok:
            blockers.append("FIREWALL_ADAPTER_ABSENT")

    return {
        "authority_state": authority_state,
        "armable": armable,
        "controller_status": controller_status,
        "blockers": blockers,
        "execution_authority": False,
    }


def build_completion_scoreboard() -> dict[str, Any]:
    """Summarize historical proof artifacts without claiming live readiness."""

    proof_done = (
        str(
            sgc.load_artifact("final_report_v209.json").get(
                "live_proof_runner_controller_status", ""
            )
        )
        == "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    )
    reconciled = (
        str(
            sgc.load_artifact("final_report_v210.json").get(
                "reconcile_runner_controller_status", ""
            )
        )
        == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
    )
    reviewed = (
        str(
            sgc.load_artifact("final_report_v211.json").get(
                "forensic_runner_controller_status", ""
            )
        )
        == "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED"
    )
    percentages = {
        "architecture_governance": 100,
        "authority_intake": 20,
        "first_live_proof": 100 if proof_done else 0,
        "reconcile_forensic": 100 if reconciled and reviewed else 0,
        "repeat_proof": 0,
        "controlled_session": 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    canonical = sgc.load_artifact("final_report_v205.json").get(
        "canonical_blocker_list", []
    )
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": round(
            sum(percentages.values()) / (len(percentages) * 100) * 100
        ),
        "remaining_blocker_count": len(canonical),
        "proof_status_count": int(proof_done) + int(reconciled) + int(reviewed),
        "proof_done": proof_done,
        "reconciled": reconciled,
        "reviewed": reviewed,
        "exact_next_action": (
            "RUN_RECONCILE_AND_FORENSICS"
            if proof_done
            else "OPERATOR_PROVIDE_APPROVAL_FILES_LIVE_SUBMIT_CAPS_AND_FIREWALL_THEN_RUN_FIRST_LIVE_PROOF"
        ),
        "execution_authority": False,
    }


__all__ = [
    "AUTHORITY_STATES",
    "NEXT_OPERATOR_ACTIONS",
    "build_activation_snapshot",
    "build_completion_scoreboard",
    "resolve_authority",
]
