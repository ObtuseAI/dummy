"""DUMMY v283 route command center V2 (read-only) — chooses next review path after proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v283 import MILESTONE

WORKSTREAM = "v283: Route Command Center V2 Repeat Session Scale Autonomy No Action"
DASH_TITLE = "Dummy V283 Route Command Center V2"
MISSION_KEY = "dummy_mission_state_report_v283"
CONTROLLER_KEY = "route_command_center_v2_controller_status"

ROUTE_OPTIONS = [
    "ROUTE_BLOCKED_NO_LIVE_PROOF",
    "ROUTE_REPEAT_REVIEW_READY",
    "ROUTE_CONTROLLED_SESSION_REVIEW_READY",
    "ROUTE_SCALE_REVIEW_BLOCKED",
    "ROUTE_AUTONOMY_REVIEW_BLOCKED",
    "ROUTE_REPAIR_REQUIRED",
]

UI_FLAGS = {
    "ui_submit_enabled": False,
    "ui_scale_enabled": False,
    "ui_autonomy_enabled": False,
    "ui_writes_enabled": False,
}

REPORT_GROUPS: dict[str, list[str]] = {
    "route-command-center-v2": ["v283_route_command_center_v2_controller_report.json"],
    "v282-baseline": ["v282_baseline_readback_v1_report.json"],
    "route-state": ["v283_route_state_report.json"],
    "ui-flags": ["v283_ui_flags_report.json"],
    "no-submit-proof": ["v283_no_submit_proof_report.json"],
    "no-scale-proof": ["v283_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v283_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v243_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v242_report.json"],
    "mission-state": ["dummy_mission_state_report_v283.json", "dashboard_v283_report_v1.json", "completion_oriented_next_action_v283_report.json"],
}

V283_ROUTES = [f"/api/v283/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Route Center", CONTROLLER_KEY], ["Route", "route_state"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    route_state = "ROUTE_REPEAT_REVIEW_READY" if st["real_proof"] else "ROUTE_BLOCKED_NO_LIVE_PROOF"
    return {
        "status": "PASS_ROUTE_COMMAND_CENTER_V2_READY_READONLY",
        "verdict": "PASS",
        "fields": {
            "route_state": route_state,
            "route_options": ROUTE_OPTIONS,
            "scale_review_blocked_by_no_live_proof": not st["real_proof"],
            "autonomy_review_blocked_by_no_live_proof": not st["real_proof"],
            **UI_FLAGS,
            "read_only_route_center": True,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [] if st["real_proof"] else ["ROUTE_BLOCKED_NO_LIVE_PROOF"],
        "next_action": "ROUTE_COMMAND_CENTER_V2_READY_READONLY_ROUTE_" + route_state + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=283, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V283_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V283ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
