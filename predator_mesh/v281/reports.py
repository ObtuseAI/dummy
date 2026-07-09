"""DUMMY v281 repeat-pilot post-proof readiness — default blocked by no live proof (PARTIAL); no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v281 import MILESTONE

WORKSTREAM = "v281: Repeat Pilot Post-Proof Readiness No Submit"
DASH_TITLE = "Dummy V281 Repeat Pilot Post-Proof Readiness"
MISSION_KEY = "dummy_mission_state_report_v281"
CONTROLLER_KEY = "repeat_pilot_post_proof_readiness_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-pilot-post-proof-readiness": ["v281_repeat_pilot_post_proof_readiness_controller_report.json"],
    "v280-baseline": ["v280_baseline_readback_v1_report.json"],
    "readiness-checks": ["v281_readiness_checks_report.json"],
    "no-submit-proof": ["v281_no_submit_proof_report.json"],
    "no-scale-proof": ["v281_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v281_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v241_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v240_report.json"],
    "mission-state": ["dummy_mission_state_report_v281.json", "dashboard_v281_report_v1.json", "completion_oriented_next_action_v281_report.json"],
}

V281_ROUTES = [f"/api/v281/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Repeat Readiness", CONTROLLER_KEY], ["State", "repeat_state"], ["Next Action", "current_next_action"]]


def _resolve(first_live_proof: bool, reconcile: bool, forensic: bool, repair_required: bool) -> tuple[str, str, str]:
    if repair_required:
        return "REPEAT_REPAIR_REQUIRED", "PARTIAL", "PARTIAL_REPEAT_POST_PROOF_READINESS_REPAIR_REQUIRED"
    if not first_live_proof:
        return "REPEAT_BLOCKED_NO_LIVE_PROOF", "PARTIAL", "PARTIAL_REPEAT_POST_PROOF_READINESS_BLOCKED_NO_LIVE_PROOF"
    if not reconcile:
        return "REPEAT_BLOCKED_NO_RECONCILE", "PARTIAL", "PARTIAL_REPEAT_POST_PROOF_READINESS_BLOCKED_NO_RECONCILE"
    if not forensic:
        return "REPEAT_BLOCKED_NO_FORENSIC", "PARTIAL", "PARTIAL_REPEAT_POST_PROOF_READINESS_BLOCKED_NO_FORENSIC"
    return "REPEAT_REVIEW_READY_LOCKED", "PASS", "PASS_REPEAT_POST_PROOF_READINESS_READY_LOCKED"


def _controller(baseline_status: str, first_live_proof: bool = False, reconcile: bool = False,
                forensic: bool = False, repair_required: bool = False, **kw: Any) -> dict[str, Any]:
    state, verdict, status = _resolve(first_live_proof, reconcile, forensic, repair_required)
    checks = {
        "first_live_proof_present": first_live_proof,
        "reconcile_present": reconcile,
        "forensic_present": forensic,
        "repeat_approval_status": "AWAIT_OPERATOR",
        "live_submit_caps_unchanged": True,
        "adapter_status": "AWAIT_OPERATOR",
        "risk_status": "OK",
        "abstention_status": "OK",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "repeat_state": state,
            "readiness_checks": checks,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "REPEAT_POST_PROOF_READINESS_" + state + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=281, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V281_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V281ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
