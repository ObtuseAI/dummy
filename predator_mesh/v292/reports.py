"""DUMMY v292 repeat/session fast-route prep after proof — default blocked by no live proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v292 import MILESTONE

WORKSTREAM = "v292: Repeat Session Fast-Route Prep After Proof"
DASH_TITLE = "Dummy V292 Repeat Session Fast-Route Prep"
MISSION_KEY = "dummy_mission_state_report_v292"
CONTROLLER_KEY = "repeat_session_fast_route_prep_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-session-fast-route-prep": ["v292_repeat_session_fast_route_prep_controller_report.json"],
    "v291-baseline": ["v291_baseline_readback_v1_report.json"],
    "fast-route-checks": ["v292_fast_route_checks_report.json"],
    "no-submit-proof": ["v292_no_submit_proof_report.json"],
    "no-scale-proof": ["v292_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v292_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v252_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v251_report.json"],
    "mission-state": ["dummy_mission_state_report_v292.json", "dashboard_v292_report_v1.json", "completion_oriented_next_action_v292_report.json"],
}

V292_ROUTES = [f"/api/v292/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Fast Route", CONTROLLER_KEY], ["State", "fast_route_state"], ["Next Action", "current_next_action"]]


def _resolve(first_proof: bool, reconcile: bool, forensic: bool, route: str, repair: bool) -> tuple[str, str, str]:
    if repair:
        return "FAST_ROUTE_REPAIR_REQUIRED", "PARTIAL", "PARTIAL_FAST_ROUTE_REPAIR_REQUIRED"
    if not first_proof:
        return "FAST_ROUTE_BLOCKED_NO_LIVE_PROOF", "PARTIAL", "PARTIAL_FAST_ROUTE_BLOCKED_NO_LIVE_PROOF"
    if not reconcile:
        return "FAST_ROUTE_BLOCKED_NO_RECONCILE", "PARTIAL", "PARTIAL_FAST_ROUTE_BLOCKED_NO_RECONCILE"
    if not forensic:
        return "FAST_ROUTE_BLOCKED_NO_FORENSIC", "PARTIAL", "PARTIAL_FAST_ROUTE_BLOCKED_NO_FORENSIC"
    if route == "session":
        return "FAST_ROUTE_SESSION_READY_LOCKED", "PASS", "PASS_REPEAT_SESSION_FAST_ROUTE_READY_LOCKED"
    return "FAST_ROUTE_REPEAT_READY_LOCKED", "PASS", "PASS_REPEAT_SESSION_FAST_ROUTE_READY_LOCKED"


def _controller(baseline_status: str, first_live_proof: bool = False, reconcile: bool = False,
                forensic: bool = False, route: str = "repeat", repair_required: bool = False, **kw: Any) -> dict[str, Any]:
    state, verdict, status = _resolve(first_live_proof, reconcile, forensic, route, repair_required)
    checks = {
        "first_proof_present": first_live_proof,
        "reconcile_present": reconcile,
        "forensic_present": forensic,
        "repeat_approval_status": "AWAIT_OPERATOR",
        "controlled_session_approval_status": "AWAIT_OPERATOR",
        "controlled_operation_approval_status": "AWAIT_OPERATOR",
        "live_submit_caps_unchanged": True,
        "adapter_status": "AWAIT_OPERATOR",
        "risk_status": "OK",
        "abstention_status": "OK",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "fast_route_state": state,
            "fast_route_checks": checks,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "REPEAT_SESSION_FAST_ROUTE_" + state + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=292, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V292_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V292ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
