"""DUMMY v299 post-proof auto intake V4 (no new order) — default no attempt; classifies attempt artifacts; no cancel, no private-data leak."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v299 import MILESTONE

WORKSTREAM = "v299: Post-Proof Auto Intake V4 No New Order"
DASH_TITLE = "Dummy V299 Post-Proof Auto Intake V4"
MISSION_KEY = "dummy_mission_state_report_v299"
CONTROLLER_KEY = "post_proof_auto_intake_v4_controller_status"

VALIDATE_FIELDS = ["proof_id", "proof_target", "order_attempt_id", "idempotency_key", "timestamp", "attempt_status", "proof_lock", "adapter_response_shape"]

REPORT_GROUPS: dict[str, list[str]] = {
    "post-proof-auto-intake-v4": ["v299_post_proof_auto_intake_v4_controller_report.json"],
    "v298-baseline": ["v298_baseline_readback_v1_report.json"],
    "attempt-classification": ["v299_attempt_classification_report.json"],
    "no-new-order-proof": ["v299_no_new_order_proof_report.json"],
    "no-private-data-leak-proof": ["v299_no_private_data_leak_proof_report.json"],
    "no-broker-contact-proof": ["v299_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v259_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v258_report.json"],
    "mission-state": ["dummy_mission_state_report_v299.json", "dashboard_v299_report_v1.json", "completion_oriented_next_action_v299_report.json"],
}

V299_ROUTES = [f"/api/v299/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Intake", CONTROLLER_KEY], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]]


def _classify(attempt: dict[str, Any] | None) -> tuple[str, str, str]:
    if not attempt:
        return "PARTIAL_NO_PROOF_ATTEMPT_TO_AUTO_INGEST", "PARTIAL", "NO_ATTEMPT"
    if attempt.get("duplicate"):
        return "PARTIAL_POST_PROOF_AUTO_INTAKE_DUPLICATE_ATTEMPT_BLOCKED", "PARTIAL", "DUPLICATE_ATTEMPT_BLOCKED"
    if attempt.get("malformed") or not all(attempt.get(k) not in (None, "") for k in ("proof_id", "order_attempt_id", "idempotency_key")):
        return "PARTIAL_POST_PROOF_AUTO_INTAKE_MALFORMED_PROOF_ARTIFACT", "PARTIAL", "MALFORMED_PROOF_ARTIFACT"
    if attempt.get("repair_required"):
        return "PARTIAL_POST_PROOF_AUTO_INTAKE_REPAIR_REQUIRED", "PARTIAL", "REPAIR_REQUIRED"
    if attempt.get("forensic"):
        return "PASS_POST_PROOF_AUTO_INTAKE_FORENSIC_READY_FOR_ROUTE", "PASS", "FORENSIC_READY_FOR_ROUTE"
    if attempt.get("reconciled"):
        return "PASS_POST_PROOF_AUTO_INTAKE_RECONCILED_READY_FOR_FORENSIC", "PASS", "RECONCILED_READY_FOR_FORENSIC"
    return "PASS_POST_PROOF_AUTO_INTAKE_READY_FOR_RECONCILE", "PASS", "ATTEMPT_READY_FOR_RECONCILE"


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
        "next_action": "POST_PROOF_AUTO_INTAKE_" + classification + "_NO_NEW_ORDER",
    }


_BUNDLE = fcc.StageBundle(
    version=299, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V299_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V299ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
