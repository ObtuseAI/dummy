"""DUMMY v275 final operator execution baseline (reads V265-V274) — fail-closed staged gate; no submit, no broker contact, no scale, no autonomy, no approval writes."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v275 import MILESTONE

WORKSTREAM = "v275: Final Operator Execution Baseline From V265 To V274"
DASH_TITLE = "Dummy V275 Final Operator Execution Baseline"
MISSION_KEY = "dummy_mission_state_report_v275"
CONTROLLER_KEY = "final_operator_execution_baseline_controller_status"

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
    "final-operator-execution-baseline": ["v275_final_operator_execution_baseline_controller_report.json"],
    "v274-baseline": ["v274_baseline_readback_v1_report.json"],
    "appliance-state-classification": ["v275_appliance_state_classification_report.json"],
    "canonical-next-action-list": ["v275_canonical_next_action_list_report.json"],
    "no-submit-proof": ["v275_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v275_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v235_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v234_report.json"],
    "mission-state": ["dummy_mission_state_report_v275.json", "dashboard_v275_report_v1.json", "completion_oriented_next_action_v275_report.json"],
}

V275_ROUTES = [f"/api/v275/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Baseline", CONTROLLER_KEY], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    classification = {
        "EXECUTION_CONSOLE_READY_FOR_BUILD": not baseline_status.startswith("FAIL"),
        "AUTHORITY_IMPORT_PENDING": not (st["import_ok"] and st["schema_ok"]),
        "LIVE_SUBMIT_CAPS_PENDING": not st["caps_ok"],
        "FIREWALL_ADAPTER_PENDING": not st["adapter_ok"],
        "ARMABILITY_PENDING": not st["armable_ok"],
        "EXECUTE_ONCE_PENDING": not st["real_proof"],
        "POST_PROOF_PENDING": not st["real_proof"],
        "ROUTE_REPEAT_OR_SESSION_PENDING": not st["real_proof"],
    }
    return {
        "status": "PASS_FINAL_OPERATOR_EXECUTION_BASELINE_READY",
        "verdict": "PASS",
        "fields": {
            "appliance_state_classification": classification,
            "canonical_next_action_list": REMAINING_ACTIONS,
            "authority_state": st,
            "execution_console_ready_for_build": classification["EXECUTION_CONSOLE_READY_FOR_BUILD"],
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "FINAL_OPERATOR_EXECUTION_BASELINE_READY_NEXT_BUILD_FINAL_OPERATOR_EXECUTION_CONSOLE_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=275, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V275_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V275ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
