"""DUMMY v289 execute-once final run wrapper V6 (full-authority only) — default not armed/no submit; fixture uses non-broker double; real order never placed by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v289 import MILESTONE

WORKSTREAM = "v289: Execute-Once Final Run Wrapper V6 Full-Auth Only"
DASH_TITLE = "Dummy V289 Execute-Once Final Run Wrapper V6"
MISSION_KEY = "dummy_mission_state_report_v289"
CONTROLLER_KEY = "execute_once_final_run_wrapper_v6_controller_status"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"

# Ordered arm-requirement checks. Each maps to a blocking reason if unmet.
ARM_CHECKS = [
    ("precheck_ready", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_PRECHECK"),
    ("env_mode", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_ENV_GATE"),
    ("env_ack", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_ENV_GATE"),
    ("live_authorized", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("resolver_armable", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("approval_exact", "FAIL_CLOSED_EXECUTE_ONCE_FINAL_RUN_APPROVAL_INVALID"),
    ("live_submit_enabled", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("caps_confirmed", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("adapter_injected", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_ADAPTER"),
    ("proof_target_valid", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("limit_only", "FAIL_CLOSED_EXECUTE_ONCE_FINAL_RUN_MARKET_ORDER_REJECTED"),
    ("idempotency_key", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY"),
    ("proof_lock_clear", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_STALE_PROOF_LOCK"),
    ("not_repeat", "EXECUTE_ONCE_FINAL_RUN_BLOCKED_REPEAT_AUTO_LOCKED"),
]

REPORT_GROUPS: dict[str, list[str]] = {
    "execute-once-final-run-wrapper-v6": ["v289_execute_once_final_run_wrapper_v6_controller_report.json"],
    "v288-baseline": ["v288_baseline_readback_v1_report.json"],
    "arm-requirements": ["v289_arm_requirements_report.json"],
    "no-fixture-inflation-proof": ["v289_no_fixture_inflation_proof_report.json"],
    "no-submit-proof": ["v289_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v289_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v249_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v248_report.json"],
    "mission-state": ["dummy_mission_state_report_v289.json", "dashboard_v289_report_v1.json", "completion_oriented_next_action_v289_report.json"],
}

V289_ROUTES = [f"/api/v289/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Execute-Once", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, arm: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    if not arm:
        return {
            "status": "PARTIAL_EXECUTE_ONCE_FINAL_RUN_NOT_ARMED",
            "verdict": "PARTIAL",
            "fields": {
                "arm_state": "NOT_ARMED_DRY_DEFAULT",
                "fixture_only": False,
                "fixture_proof_inflates_real_score": False,
                "real_live_orders_submitted": 0,
                "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
                "no_submit_proof_status": "PASS_NO_SUBMIT",
                "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            },
            "blockers": ["EXECUTE_ONCE_FINAL_RUN_NOT_ARMED_DRY_DEFAULT"],
            "next_action": "EXECUTE_ONCE_FINAL_RUN_NOT_ARMED_NEXT_RUN_NO_SURPRISES_PRECHECK_THEN_OPERATOR_FULL_AUTHORITY_NO_SUBMIT_BY_DUMMY",
        }
    # Fixture path: evaluate arm requirements. Any unmet -> blocked. All met -> non-broker double submit.
    for key, block_status in ARM_CHECKS:
        if not arm.get(key):
            return {
                "status": block_status,
                "verdict": "PARTIAL",
                "fields": {
                    "arm_state": "BLOCKED",
                    "block_requirement": key,
                    "fixture_only": True,
                    "fixture_proof_inflates_real_score": False,
                    "real_live_orders_submitted": 0,
                    "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
                    "no_submit_proof_status": "PASS_NO_SUBMIT",
                    "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
                },
                "blockers": [block_status],
                "next_action": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_" + key.upper() + "_NO_SUBMIT_BY_DUMMY",
            }
    # All requirements met via fixture non-broker double.
    return {
        "status": "PASS_EXECUTE_ONCE_FINAL_RUN_SUBMITTED_AUTOLOCKED",
        "verdict": "PASS",
        "fields": {
            "arm_state": "SUBMITTED_AUTOLOCKED_NON_BROKER_DOUBLE",
            "fixture_only": True,
            "uses_non_broker_double": True,
            "submitted_autolocked": True,
            "real_live_orders": 0,
            "real_broker_contacted": False,
            "market_order_submitted": False,
            "max_attempts": 1,
            "fixture_proof_inflates_real_score": False,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "EXECUTE_ONCE_FINAL_RUN_SUBMITTED_AUTOLOCKED_FIXTURE_ONLY_NEXT_RUN_POST_PROOF_AUTOPILOT_INTAKE_NO_NEW_ORDER",
    }


_BUNDLE = fcc.StageBundle(
    version=289, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V289_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


def full_authority_arm() -> dict[str, Any]:
    """A complete fixture arm packet (all checks met) used by tests only. Non-broker double downstream."""
    return {k: True for k, _ in ARM_CHECKS} | {"env_mode": True, "env_ack": True}


class V289ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
