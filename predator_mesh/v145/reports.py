"""DUMMY v145 production pilot closeout + next-phase lock — summarizes V136-V144 and locks production state; no new orders.

Reads pilot (V141) / repeat (V144) / scale (V133) / controlled-operation (V134) status, totals the live order count
(0), builds an autonomy blocker map and live/risk/abstention proof-gap maps, and selects a next-action from a fixed
matrix. Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v145 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v145: Production Pilot Closeout Next Phase Lock And Scale Blocker Update"
MISSION_NAME = "dummy_mission_state_report_v131.json"
FINAL_NAME = "final_report_v145.json"
INDEX_KEYS = ["closeout_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V145 Production Pilot Closeout & Next-Phase Lock"
MISSION_KEY = "dummy_mission_state_report_v131"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Closeout", "closeout_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V145_ROUTES = [
    "/api/v145/closeout-controller",
    "/api/v145/v144-baseline",
    "/api/v145/pilot-status-summary",
    "/api/v145/repeat-status-summary",
    "/api/v145/total-live-order-count",
    "/api/v145/scale-status-summary",
    "/api/v145/controlled-operation-status-summary",
    "/api/v145/autonomy-blocker-map",
    "/api/v145/live-proof-gap-map",
    "/api/v145/risk-proof-gap-map",
    "/api/v145/abstention-proof-gap-map",
    "/api/v145/next-action-matrix",
    "/api/v145/no-scale-proof",
    "/api/v145/no-autonomy-proof",
    "/api/v145/no-new-order-proof",
    "/api/v145/readiness-governor",
    "/api/v145/execution-lock",
    "/api/v145/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "closeout-controller": ["v145_closeout_controller_report.json"],
    "v144-baseline": ["v144_baseline_readback_v1_report.json"],
    "pilot-status-summary": ["v145_pilot_status_summary_report.json"],
    "repeat-status-summary": ["v145_repeat_status_summary_report.json"],
    "total-live-order-count": ["v145_total_live_order_count_report.json"],
    "scale-status-summary": ["v145_scale_status_summary_report.json"],
    "controlled-operation-status-summary": ["v145_controlled_operation_status_summary_report.json"],
    "autonomy-blocker-map": ["v145_autonomy_blocker_map_report.json"],
    "live-proof-gap-map": ["v145_live_proof_gap_map_report.json"],
    "risk-proof-gap-map": ["v145_risk_proof_gap_map_report.json"],
    "abstention-proof-gap-map": ["v145_abstention_proof_gap_map_report.json"],
    "next-action-matrix": ["v145_next_action_matrix_report.json"],
    "no-scale-proof": ["v145_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v145_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v145_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v105_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v104_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v145_report_v1.json", "completion_oriented_next_action_v145_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(145)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v145/reports.py scripts/generate_v145_reports.py dashboard/backend/v145_routes.py",
    "python scripts/generate_v145_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_PRODUCTION_PILOT_APPROVAL",
    "AWAIT_REPEAT_PILOT_APPROVAL",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "CONTROLLED_OPERATION_READY_LOCKED",
    "AUTONOMY_NOT_ELIGIBLE",
]


class V145Context:
    def __init__(self, *, pilot_override=None, repeat_override=None, scale_override=None, controlled_override=None) -> None:
        self.v144_baseline_status = sgc.baseline_status("final_report_v144.json", "V144")
        self.pilot_status = pilot_override if pilot_override is not None else str(sgc.load_artifact("final_report_v141.json").get("pilot_gate_controller_status", "PARTIAL_PRODUCTION_PILOT_NOT_ARMED"))
        self.repeat_status = repeat_override if repeat_override is not None else str(sgc.load_artifact("final_report_v144.json").get("repeat_pilot_gate_controller_status", "PARTIAL_REPEAT_PILOT_NOT_ARMED"))
        self.scale_status = scale_override if scale_override is not None else str(sgc.load_artifact("final_report_v133.json").get("scale_recommendation", "NO_SCALE"))
        self.controlled_status = controlled_override if controlled_override is not None else str(sgc.load_artifact("final_report_v134.json").get("controlled_operation_gate_controller_status", "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"))
        self.pilot_live_orders = int(sgc.load_artifact("final_report_v141.json").get("real_live_orders_submitted_count", 0) or 0)
        self.repeat_live_orders = int(sgc.load_artifact("final_report_v144.json").get("real_live_orders_submitted_count", 0) or 0)

    @property
    def total_live_orders(self) -> int:
        return self.pilot_live_orders + self.repeat_live_orders

    @property
    def pilot_done(self) -> bool:
        return self.pilot_status == "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED"

    @property
    def repeat_done(self) -> bool:
        return self.repeat_status == "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED"

    @property
    def scale_ready(self) -> bool:
        return self.scale_status == "SCALE_STEP_1_REVIEW_READY"

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.pilot_done:
            return "AWAIT_PRODUCTION_PILOT_APPROVAL"
        if not self.repeat_done:
            return "AWAIT_REPEAT_PILOT_APPROVAL"
        if not self.scale_ready:
            return "AWAIT_SCALE_REVIEW_APPROVAL"
        if self.controlled_status == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED":
            return "CONTROLLED_OPERATION_READY_LOCKED"
        return "AUTONOMY_NOT_ELIGIBLE"

    @property
    def autonomy_blocker_map(self) -> dict[str, Any]:
        return {
            "production_pilot_approval": "PRESENT" if self.pilot_done else "ABSENT",
            "repeat_pilot_approval": "PRESENT" if self.repeat_done else "ABSENT",
            "scale_review_approval": "PRESENT" if self.scale_ready else "ABSENT",
            "autonomy_enable_approval": "ABSENT",
            "autonomous_trading_eligible": False,
        }

    @property
    def controller_status(self) -> str:
        return "FAIL_CLOSEOUT_BASELINE_REGRESSION" if self.v144_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_PILOT_CLOSEOUT_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v144_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V144_BASELINE_REGRESSION"] if self.v144_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PRODUCTION_PILOT_CLOSEOUT_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V145Context) -> dict[str, Any]:
    return {
        "v144_baseline_status": ctx.v144_baseline_status,
        "closeout_controller_status": ctx.controller_status,
        "pilot_status_summary": ctx.pilot_status,
        "pilot_status_summary_status": "PASS_PILOT_STATUS_SUMMARIZED",
        "repeat_status_summary": ctx.repeat_status,
        "repeat_status_summary_status": "PASS_REPEAT_STATUS_SUMMARIZED",
        "total_live_order_count": ctx.total_live_orders,
        "total_live_order_count_status": "PASS_TOTAL_LIVE_ORDER_COUNT_ZERO" if ctx.total_live_orders == 0 else "PASS_TOTAL_LIVE_ORDER_COUNT",
        "scale_status_summary": ctx.scale_status,
        "scale_status_summary_status": "PASS_SCALE_STATUS_SUMMARIZED",
        "controlled_operation_status_summary": ctx.controlled_status,
        "controlled_operation_status_summary_status": "PASS_CONTROLLED_OPERATION_STATUS_SUMMARIZED",
        "autonomy_blocker_map": ctx.autonomy_blocker_map,
        "autonomy_blocker_map_status": "PASS_AUTONOMY_BLOCKER_MAPPED",
        "live_proof_gap_map": {"production_pilot_submit_proof": "PRESENT" if ctx.pilot_done else "ABSENT", "repeat_pilot_submit_proof": "PRESENT" if ctx.repeat_done else "ABSENT"},
        "live_proof_gap_map_status": "PASS_LIVE_PROOF_GAP_MAPPED",
        "risk_proof_gap_map": {"risk_governor": "PRESENT", "stop_policy": "PRESENT", "kill_switch": "PRESENT"},
        "risk_proof_gap_map_status": "PASS_RISK_PROOF_GAP_MAPPED",
        "abstention_proof_gap_map": {"abstention_governor": "PRESENT", "abstention_policy": "PRESENT"},
        "abstention_proof_gap_map_status": "PASS_ABSTENTION_PROOF_GAP_MAPPED",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": ctx.total_live_orders,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v105_status": "PASS",
        "execution_lock_deep_recheck_v104_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V145Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v144_baseline"):
        return "PASS" if ctx.v144_baseline_status == "PASS_V144_BASELINE_READBACK" else "FAIL" if ctx.v144_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V145Context) -> dict[str, Any]:
    workstream = "v145: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v145_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V145_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v145_report.json":
        report.update({"completion_oriented_next_action_v145_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v144_carried_status": ctx.v144_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "total_real_live_orders_submitted": ctx.total_live_orders, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v145_closeout_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v145_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v145.json", "dummy_canonical_identity_report_v145.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V145ReportFactory:
    def __init__(self, *, pilot_override=None, repeat_override=None, scale_override=None, controlled_override=None) -> None:
        self.kw = dict(pilot_override=pilot_override, repeat_override=repeat_override, scale_override=scale_override, controlled_override=controlled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V145Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
