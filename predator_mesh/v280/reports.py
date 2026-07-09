"""DUMMY v280 post-proof reconcile/forensic launcher — default no proof (PARTIAL); no new order, no cancel, no broker contact."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v280 import MILESTONE

WORKSTREAM = "v280: Post-Proof Reconcile Forensic Launcher No New Order"
DASH_TITLE = "Dummy V280 Post-Proof Reconcile Forensic Launcher"
MISSION_KEY = "dummy_mission_state_report_v280"
CONTROLLER_KEY = "post_proof_reconcile_forensic_launcher_controller_status"

LAUNCHER_STEPS = [
    {"step": 1, "action": "run proof intake handoff"},
    {"step": 2, "action": "run reconcile"},
    {"step": 3, "action": "run forensic"},
    {"step": 4, "action": "update proof state artifact"},
    {"step": 5, "action": "update route readiness"},
    {"step": 6, "action": "update completion scoreboard"},
]

REPORT_GROUPS: dict[str, list[str]] = {
    "post-proof-reconcile-forensic-launcher": ["v280_post_proof_reconcile_forensic_launcher_controller_report.json"],
    "v279-baseline": ["v279_baseline_readback_v1_report.json"],
    "launcher-steps": ["v280_launcher_steps_report.json"],
    "no-new-order-proof": ["v280_no_new_order_proof_report.json"],
    "no-broker-contact-proof": ["v280_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v240_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v239_report.json"],
    "mission-state": ["dummy_mission_state_report_v280.json", "dashboard_v280_report_v1.json", "completion_oriented_next_action_v280_report.json"],
}

V280_ROUTES = [f"/api/v280/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Launcher", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, proof: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    if not proof:
        status, verdict, proof_state = "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC", "PARTIAL", "NO_PROOF"
        next_action = "POST_PROOF_RECONCILE_FORENSIC_LAUNCHER_NO_PROOF_NEXT_RUN_EXECUTE_ONCE_WITH_AUTHORITY_NO_NEW_ORDER"
        blockers = ["NO_PROOF_TO_RECONCILE_FORENSIC"]
        scoreboard = False
    else:
        status, verdict, proof_state = "PASS_POST_PROOF_RECONCILE_FORENSIC_LAUNCHER_REVIEWED_LOCKED", "PASS", "PROOF_RECONCILED_FORENSIC_REVIEWED_LOCKED"
        next_action = "POST_PROOF_RECONCILE_FORENSIC_LAUNCHER_REVIEWED_LOCKED_NEXT_ROUTE_REPEAT_OR_SESSION_NO_SUBMIT"
        blockers = []
        scoreboard = True
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "launcher_steps": LAUNCHER_STEPS,
            "proof_state": proof_state,
            "route_readiness_updated": scoreboard,
            "completion_scoreboard_updated": scoreboard,
            "proof_present": bool(proof),
            "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
            "no_cancel_by_default": True,
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": blockers,
        "next_action": next_action,
    }


_BUNDLE = fcc.StageBundle(
    version=280, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V280_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V280ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
