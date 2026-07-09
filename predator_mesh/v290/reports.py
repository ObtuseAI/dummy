"""DUMMY v290 post-proof autopilot intake (no new order) — default no attempt; classifies attempt artifacts; no cancel, no private-data leak."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v290 import MILESTONE

WORKSTREAM = "v290: Post-Proof Autopilot Intake No New Order"
DASH_TITLE = "Dummy V290 Post-Proof Autopilot Intake"
MISSION_KEY = "dummy_mission_state_report_v290"
CONTROLLER_KEY = "post_proof_autopilot_intake_controller_status"

VALIDATE_FIELDS = ["proof_id", "proof_target", "order_attempt_id", "idempotency_key", "timestamp", "attempt_status", "proof_lock", "adapter_response_shape"]

REPORT_GROUPS: dict[str, list[str]] = {
    "post-proof-autopilot-intake": ["v290_post_proof_autopilot_intake_controller_report.json"],
    "v289-baseline": ["v289_baseline_readback_v1_report.json"],
    "attempt-classification": ["v290_attempt_classification_report.json"],
    "no-new-order-proof": ["v290_no_new_order_proof_report.json"],
    "no-private-data-leak-proof": ["v290_no_private_data_leak_proof_report.json"],
    "no-broker-contact-proof": ["v290_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v250_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v249_report.json"],
    "mission-state": ["dummy_mission_state_report_v290.json", "dashboard_v290_report_v1.json", "completion_oriented_next_action_v290_report.json"],
}

V290_ROUTES = [f"/api/v290/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Intake", CONTROLLER_KEY], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]]


def _classify(attempt: dict[str, Any] | None) -> tuple[str, str, str]:
    if not attempt:
        return "PARTIAL_NO_PROOF_ATTEMPT_TO_AUTOPILOT_INGEST", "PARTIAL", "NO_ATTEMPT"
    if attempt.get("duplicate"):
        return "PARTIAL_POST_PROOF_AUTOPILOT_INTAKE_DUPLICATE_ATTEMPT_BLOCKED", "PARTIAL", "DUPLICATE_ATTEMPT_BLOCKED"
    if attempt.get("malformed") or not all(attempt.get(k) not in (None, "") for k in ("proof_id", "order_attempt_id", "idempotency_key")):
        return "PARTIAL_POST_PROOF_AUTOPILOT_INTAKE_MALFORMED_PROOF_ARTIFACT", "PARTIAL", "MALFORMED_PROOF_ARTIFACT"
    if attempt.get("repair_required"):
        return "PARTIAL_POST_PROOF_AUTOPILOT_INTAKE_REPAIR_REQUIRED", "PARTIAL", "REPAIR_REQUIRED"
    if attempt.get("reconciled"):
        return "PASS_POST_PROOF_AUTOPILOT_INTAKE_RECONCILED_READY_FOR_FORENSIC", "PASS", "RECONCILED_READY_FOR_FORENSIC"
    return "PASS_POST_PROOF_AUTOPILOT_INTAKE_READY_FOR_RECONCILE", "PASS", "ATTEMPT_READY_FOR_RECONCILE"


def _controller(baseline_status: str, attempt: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    status, verdict, classification = _classify(attempt)
    validated = {k: (attempt or {}).get(k) for k in VALIDATE_FIELDS}
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "attempt_classification": classification,
            "validated_attempt": validated,
            "attempt_present": bool(attempt),
            "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
            "no_cancel_by_default": True,
            "no_private_data_leak_proof_status": "PASS_NO_PRIVATE_DATA_LEAK",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [] if verdict == "PASS" else [classification],
        "next_action": "POST_PROOF_AUTOPILOT_INTAKE_" + classification + "_NO_NEW_ORDER",
    }


_BUNDLE = fcc.StageBundle(
    version=290, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V290_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V290ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
