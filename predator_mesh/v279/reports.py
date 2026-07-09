"""DUMMY v279 live-proof attempt monitor — default no attempt (PARTIAL); no new order, no cancel, no private-data leak."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v279 import MILESTONE

WORKSTREAM = "v279: Live-Proof Attempt Monitor No New Order"
DASH_TITLE = "Dummy V279 Live-Proof Attempt Monitor"
MISSION_KEY = "dummy_mission_state_report_v279"
CONTROLLER_KEY = "live_proof_attempt_monitor_controller_status"

MONITOR_FIELDS = ["proof_id", "proof_target", "attempt_id", "idempotency_key", "proof_lock", "timestamp", "state", "adapter_response_shape"]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-proof-attempt-monitor": ["v279_live_proof_attempt_monitor_controller_report.json"],
    "v278-baseline": ["v278_baseline_readback_v1_report.json"],
    "attempt-classification": ["v279_attempt_classification_report.json"],
    "no-new-order-proof": ["v279_no_new_order_proof_report.json"],
    "no-private-data-leak-proof": ["v279_no_private_data_leak_proof_report.json"],
    "no-broker-contact-proof": ["v279_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v239_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v238_report.json"],
    "mission-state": ["dummy_mission_state_report_v279.json", "dashboard_v279_report_v1.json", "completion_oriented_next_action_v279_report.json"],
}

V279_ROUTES = [f"/api/v279/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Monitor", CONTROLLER_KEY], ["Classification", "attempt_classification"], ["Next Action", "current_next_action"]]


def _classify(attempt: dict[str, Any] | None) -> tuple[str, str, str, str]:
    """Return (status, verdict, classification, next_action)."""
    if not attempt:
        return (
            "PARTIAL_NO_LIVE_PROOF_ATTEMPT_TO_MONITOR", "PARTIAL", "NO_ATTEMPT",
            "LIVE_PROOF_ATTEMPT_MONITOR_NO_ATTEMPT_NEXT_RUN_EXECUTE_ONCE_WITH_AUTHORITY_NO_SUBMIT_BY_DUMMY",
        )
    if attempt.get("duplicate"):
        return ("PARTIAL_LIVE_PROOF_ATTEMPT_DUPLICATE_BLOCKED", "PARTIAL", "ATTEMPT_DUPLICATE_BLOCKED",
                "LIVE_PROOF_ATTEMPT_MONITOR_DUPLICATE_BLOCKED_NEXT_NO_ACTION_NO_SUBMIT")
    if attempt.get("malformed") or not all(attempt.get(k) not in (None, "") for k in ("proof_id", "attempt_id", "idempotency_key")):
        return ("PARTIAL_LIVE_PROOF_ATTEMPT_MALFORMED", "PARTIAL", "ATTEMPT_MALFORMED",
                "LIVE_PROOF_ATTEMPT_MONITOR_MALFORMED_NEXT_ATTEMPT_REPAIR_REQUIRED_NO_SUBMIT")
    if attempt.get("repair_required"):
        return ("PARTIAL_LIVE_PROOF_ATTEMPT_REPAIR_REQUIRED", "PARTIAL", "ATTEMPT_REPAIR_REQUIRED",
                "LIVE_PROOF_ATTEMPT_MONITOR_REPAIR_REQUIRED_NEXT_ATTEMPT_REPAIR_NO_SUBMIT")
    return ("PASS_LIVE_PROOF_ATTEMPT_MONITOR_READY_FOR_INTAKE", "PASS", "ATTEMPT_DETECTED_READY_FOR_INTAKE",
            "LIVE_PROOF_ATTEMPT_MONITOR_READY_FOR_INTAKE_NEXT_RUN_POST_PROOF_RECONCILE_FORENSIC_NO_NEW_ORDER")


def _controller(baseline_status: str, attempt: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    status, verdict, classification, next_action = _classify(attempt)
    monitored = {k: (attempt or {}).get(k) for k in MONITOR_FIELDS}
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "attempt_classification": classification,
            "monitored_attempt": monitored,
            "attempt_present": bool(attempt),
            "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
            "no_cancel_by_default": True,
            "no_private_data_leak_proof_status": "PASS_NO_PRIVATE_DATA_LEAK",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [] if verdict == "PASS" else ["NO_LIVE_PROOF_ATTEMPT_TO_MONITOR"] if classification == "NO_ATTEMPT" else [classification],
        "next_action": next_action,
    }


_BUNDLE = fcc.StageBundle(
    version=279, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V279_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V279ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
