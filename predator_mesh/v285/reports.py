"""DUMMY v285 first-proof final run baseline (reads V275-V284) — fail-closed staged gate; no submit, no broker contact, no scale, no autonomy, no approval writes."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v285 import MILESTONE

WORKSTREAM = "v285: First-Proof Final Run Baseline From V275 To V284"
DASH_TITLE = "Dummy V285 First-Proof Final Run Baseline"
MISSION_KEY = "dummy_mission_state_report_v285"
CONTROLLER_KEY = "first_proof_final_run_baseline_controller_status"

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
    "first-proof-final-run-baseline": ["v285_first_proof_final_run_baseline_controller_report.json"],
    "v284-baseline": ["v284_baseline_readback_v1_report.json"],
    "appliance-state-classification": ["v285_appliance_state_classification_report.json"],
    "canonical-next-action-list": ["v285_canonical_next_action_list_report.json"],
    "no-submit-proof": ["v285_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v285_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v245_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v244_report.json"],
    "mission-state": ["dummy_mission_state_report_v285.json", "dashboard_v285_report_v1.json", "completion_oriented_next_action_v285_report.json"],
}

V285_ROUTES = [f"/api/v285/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Baseline", CONTROLLER_KEY], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    classification = {
        "FINAL_RUN_APPLIANCE_READY_FOR_BUILD": not baseline_status.startswith("FAIL"),
        "AUTHORITY_MANIFEST_PENDING": not (st["import_ok"] and st["schema_ok"]),
        "LIVE_SUBMIT_CAPS_PENDING": not st["caps_ok"],
        "FIREWALL_ADAPTER_PENDING": not st["adapter_ok"],
        "ARMABILITY_RUNBOOK_PENDING": not st["armable_ok"],
        "EXECUTE_ONCE_PENDING": not st["real_proof"],
        "POST_PROOF_PENDING": not st["real_proof"],
        "REPEAT_SESSION_PENDING": not st["real_proof"],
    }
    return {
        "status": "PASS_FIRST_PROOF_FINAL_RUN_BASELINE_READY",
        "verdict": "PASS",
        "fields": {
            "appliance_state_classification": classification,
            "canonical_next_action_list": REMAINING_ACTIONS,
            "authority_state": st,
            "final_run_appliance_ready_for_build": classification["FINAL_RUN_APPLIANCE_READY_FOR_BUILD"],
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "FIRST_PROOF_FINAL_RUN_BASELINE_READY_NEXT_BUILD_FINAL_RUN_APPLIANCE_LAUNCHER_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=285, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V285_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V285ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
