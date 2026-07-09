"""DUMMY v302 repeat/session bundle prep after real proof — default blocked by no real proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v302 import MILESTONE

WORKSTREAM = "v302: Repeat Session Bundle Prep After Real Proof No Submit"
DASH_TITLE = "Dummy V302 Repeat Session Bundle Prep"
MISSION_KEY = "dummy_mission_state_report_v302"
CONTROLLER_KEY = "repeat_session_bundle_prep_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-session-bundle-prep": ["v302_repeat_session_bundle_prep_controller_report.json"],
    "v301-baseline": ["v301_baseline_readback_v1_report.json"],
    "bundle-prep-inputs": ["v302_bundle_prep_inputs_report.json"],
    "no-submit-proof": ["v302_no_submit_proof_report.json"],
    "no-scale-proof": ["v302_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v302_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v262_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v261_report.json"],
    "mission-state": ["dummy_mission_state_report_v302.json", "dashboard_v302_report_v1.json", "completion_oriented_next_action_v302_report.json"],
}

V302_ROUTES = [f"/api/v302/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Bundle Prep", CONTROLLER_KEY], ["State", "bundle_prep_state"], ["Next Action", "current_next_action"]]


def _resolve(real_proof: bool, reconcile: bool, forensic: bool, route: str, repair: bool) -> tuple[str, str, str]:
    if repair:
        return "BUNDLE_PREP_REPAIR_REQUIRED", "PARTIAL", "PARTIAL_BUNDLE_PREP_REPAIR_REQUIRED"
    if not (real_proof and reconcile and forensic):
        return "BUNDLE_PREP_BLOCKED_NO_REAL_PROOF", "PARTIAL", "PARTIAL_BUNDLE_PREP_BLOCKED_NO_REAL_PROOF"
    if route == "session":
        return "BUNDLE_PREP_SESSION_READY_LOCKED", "PASS", "PASS_REPEAT_SESSION_BUNDLE_PREP_READY_LOCKED"
    return "BUNDLE_PREP_REPEAT_READY_LOCKED", "PASS", "PASS_REPEAT_SESSION_BUNDLE_PREP_READY_LOCKED"


def _controller(baseline_status: str, real_proof: bool = False, reconcile: bool = False, forensic: bool = False,
                route: str = "repeat", repair_required: bool = False, **kw: Any) -> dict[str, Any]:
    state, verdict, status = _resolve(real_proof, reconcile, forensic, route, repair_required)
    ready = verdict == "PASS"
    inputs = {
        "repeat_pilot_next_bundle_inputs_v302": {"prepared": ready and route != "session", "requires_operator_approval": True} if ready else {"prepared": False},
        "controlled_session_next_bundle_inputs_v302": {"prepared": ready and route == "session", "requires_operator_approval": True} if ready else {"prepared": False},
        "real_proof_present": real_proof,
        "reconcile_complete": reconcile,
        "forensic_complete": forensic,
        "route_decision": route,
        "required_approvals": "AWAIT_OPERATOR",
        "live_submit_caps_unchanged": True,
        "adapter_status": "AWAIT_OPERATOR",
        "risk_status": "OK",
        "abstention_status": "OK",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "bundle_prep_state": state,
            "bundle_prep_inputs": inputs,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "REPEAT_SESSION_BUNDLE_PREP_" + state + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=302, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V302_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V302ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
