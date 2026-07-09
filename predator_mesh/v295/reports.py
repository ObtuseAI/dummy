"""DUMMY v295 real-proof dependency cutoff baseline (reads V285-V294) — declares architecture/proof fork; no submit, no broker contact, no scale, no autonomy, no approval writes."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v295 import MILESTONE

WORKSTREAM = "v295: Real-Proof Dependency Cutoff Baseline From V285 To V294"
DASH_TITLE = "Dummy V295 Real-Proof Dependency Cutoff Baseline"
MISSION_KEY = "dummy_mission_state_report_v295"
CONTROLLER_KEY = "real_proof_dependency_cutoff_baseline_controller_status"

REMAINING_ACTIONS = [
    "OPERATOR_CREATE_AUTHORITY_MANIFEST",
    "OPERATOR_CONFIGURE_LIVE_SUBMIT_CAPS",
    "OPERATOR_INJECT_FIREWALL_ADAPTER",
    "RUN_EXTERNAL_AUTHORITY_IMPORT_WIZARD",
    "RUN_FINAL_ARMABILITY_RUNBOOK",
    "RUN_EXECUTE_ONCE_RUNBOOK_WITH_AUTHORITY",
    "RUN_PROOF_INTAKE_RECONCILE_HANDOFF",
    "RUN_RECONCILE_FORENSIC",
    "ROUTE_REPEAT_OR_SESSION",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "real-proof-dependency-cutoff-baseline": ["v295_real_proof_dependency_cutoff_baseline_controller_report.json"],
    "v294-baseline": ["v294_baseline_readback_v1_report.json"],
    "fork-classification": ["v295_fork_classification_report.json"],
    "canonical-next-action-list": ["v295_canonical_next_action_list_report.json"],
    "no-submit-proof": ["v295_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v295_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v255_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v254_report.json"],
    "mission-state": ["dummy_mission_state_report_v295.json", "dashboard_v295_report_v1.json", "completion_oriented_next_action_v295_report.json"],
}

V295_ROUTES = [f"/api/v295/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Cutoff", CONTROLLER_KEY], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    authority_present = st["import_ok"] and st["schema_ok"] and st["caps_ok"] and st["adapter_ok"] and st["armable_ok"]
    classification = {
        "ARCHITECTURE_SUFFICIENT_FOR_FIRST_PROOF": not baseline_status.startswith("FAIL"),
        "REAL_PROOF_DEPENDENCY_ACTIVE": not st["real_proof"],
        "EXTERNAL_AUTHORITY_REQUIRED": not authority_present,
        "OPERATOR_EXECUTION_FORK_READY": True,
        "SCALE_AUTONOMY_BLOCKED_NO_REAL_PROOF": not st["real_proof"],
    }
    return {
        "status": "PASS_REAL_PROOF_DEPENDENCY_CUTOFF_BASELINE_READY",
        "verdict": "PASS",
        "fields": {
            "fork_classification": classification,
            "canonical_next_action_list": REMAINING_ACTIONS,
            "authority_state": st,
            "authority_present": authority_present,
            "real_proof_dependency_active": not st["real_proof"],
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "REAL_PROOF_DEPENDENCY_CUTOFF_BASELINE_READY_NEXT_OPERATOR_EXECUTION_FORK_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=295, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V295_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V295ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
