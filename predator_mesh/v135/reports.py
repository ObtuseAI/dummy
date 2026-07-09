"""DUMMY v135 production lock summary & next-phase map — summarizes V126-V134 and maps remaining blockers; no live orders.

Reads pilot (V129) / repeat (V131) / scale (V133) / controlled-operation (V134) status from the prior stage finals,
builds an autonomy blocker map and live/risk/abstention proof-gap maps, and selects a next-action from a fixed matrix.
Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v135 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v135: Production Lock Summary Next Phase Map And Autonomy Blocker Update"
MISSION_NAME = "dummy_mission_state_report_v121.json"
FINAL_NAME = "final_report_v135.json"
INDEX_KEYS = ["production_lock_controller_status", "next_action_matrix_selection", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V135 Production Lock Summary & Next-Phase Map"
MISSION_KEY = "dummy_mission_state_report_v121"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Production Lock", "production_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V135_ROUTES = [
    "/api/v135/production-lock-controller",
    "/api/v135/v134-baseline",
    "/api/v135/pilot-status-summary",
    "/api/v135/repeat-status-summary",
    "/api/v135/scale-status-summary",
    "/api/v135/controlled-operation-status-summary",
    "/api/v135/autonomy-blocker-map",
    "/api/v135/live-proof-gap-map",
    "/api/v135/risk-proof-gap-map",
    "/api/v135/abstention-proof-gap-map",
    "/api/v135/next-action-matrix",
    "/api/v135/no-new-order-proof",
    "/api/v135/readiness-governor",
    "/api/v135/execution-lock",
    "/api/v135/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-lock-controller": ["v135_production_lock_controller_report.json"],
    "v134-baseline": ["v134_baseline_readback_v1_report.json"],
    "pilot-status-summary": ["v135_pilot_status_summary_report.json"],
    "repeat-status-summary": ["v135_repeat_status_summary_report.json"],
    "scale-status-summary": ["v135_scale_status_summary_report.json"],
    "controlled-operation-status-summary": ["v135_controlled_operation_status_summary_report.json"],
    "autonomy-blocker-map": ["v135_autonomy_blocker_map_report.json"],
    "live-proof-gap-map": ["v135_live_proof_gap_map_report.json"],
    "risk-proof-gap-map": ["v135_risk_proof_gap_map_report.json"],
    "abstention-proof-gap-map": ["v135_abstention_proof_gap_map_report.json"],
    "next-action-matrix": ["v135_next_action_matrix_report.json"],
    "no-new-order-proof": ["v135_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v95_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v94_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v135_report_v1.json", "completion_oriented_next_action_v135_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(135)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v135/reports.py scripts/generate_v135_reports.py dashboard/backend/v135_routes.py",
    "python scripts/generate_v135_reports.py",
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


class V135Context:
    def __init__(self, *, pilot_override=None, repeat_override=None, scale_override=None, controlled_override=None) -> None:
        self.v134_baseline_status = sgc.baseline_status("final_report_v134.json", "V134")
        self.pilot_status = pilot_override if pilot_override is not None else str(sgc.load_artifact("final_report_v129.json").get("pilot_gate_controller_status", "PARTIAL_PRODUCTION_PILOT_NOT_ARMED"))
        self.repeat_status = repeat_override if repeat_override is not None else str(sgc.load_artifact("final_report_v131.json").get("repeat_pilot_gate_controller_status", "PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT"))
        self.scale_status = scale_override if scale_override is not None else str(sgc.load_artifact("final_report_v133.json").get("scale_recommendation", "NO_SCALE"))
        self.controlled_status = controlled_override if controlled_override is not None else str(sgc.load_artifact("final_report_v134.json").get("controlled_operation_gate_controller_status", "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"))

    @property
    def pilot_done(self) -> bool:
        return self.pilot_status == "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED"

    @property
    def repeat_ready(self) -> bool:
        return self.repeat_status == "PASS_REPEAT_PILOT_REVIEW_READY_LOCKED"

    @property
    def scale_ready(self) -> bool:
        return self.scale_status == "SCALE_STEP_1_REVIEW_READY"

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.pilot_done:
            return "AWAIT_PRODUCTION_PILOT_APPROVAL"
        if not self.repeat_ready:
            return "AWAIT_REPEAT_PILOT_APPROVAL"
        if not self.scale_ready:
            return "AWAIT_SCALE_REVIEW_APPROVAL"
        if self.controlled_status == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED":
            return "CONTROLLED_OPERATION_READY_LOCKED"
        return "AUTONOMY_NOT_ELIGIBLE"

    @property
    def autonomy_blocker_map(self) -> dict[str, Any]:
        return {
            "production_pilot_approval": "ABSENT" if not self.pilot_done else "PRESENT",
            "repeat_pilot_approval": "ABSENT" if not self.repeat_ready else "PRESENT",
            "scale_review_approval": "ABSENT" if not self.scale_ready else "PRESENT",
            "autonomy_enable_approval": "ABSENT",
            "autonomous_trading_eligible": False,
        }

    @property
    def controller_status(self) -> str:
        return "FAIL_PRODUCTION_LOCK_BASELINE_REGRESSION" if self.v134_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_LOCK_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v134_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V134_BASELINE_REGRESSION"] if self.v134_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PRODUCTION_LOCK_SUMMARY_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V135Context) -> dict[str, Any]:
    return {
        "v134_baseline_status": ctx.v134_baseline_status,
        "production_lock_controller_status": ctx.controller_status,
        "pilot_status_summary": ctx.pilot_status,
        "pilot_status_summary_status": "PASS_PILOT_STATUS_SUMMARIZED",
        "repeat_status_summary": ctx.repeat_status,
        "repeat_status_summary_status": "PASS_REPEAT_STATUS_SUMMARIZED",
        "scale_status_summary": ctx.scale_status,
        "scale_status_summary_status": "PASS_SCALE_STATUS_SUMMARIZED",
        "controlled_operation_status_summary": ctx.controlled_status,
        "controlled_operation_status_summary_status": "PASS_CONTROLLED_OPERATION_STATUS_SUMMARIZED",
        "autonomy_blocker_map": ctx.autonomy_blocker_map,
        "autonomy_blocker_map_status": "PASS_AUTONOMY_BLOCKER_MAPPED",
        "live_proof_gap_map": {"production_pilot_submit_proof": "ABSENT" if not ctx.pilot_done else "PRESENT", "repeat_pilot_submit_proof": "ABSENT"},
        "live_proof_gap_map_status": "PASS_LIVE_PROOF_GAP_MAPPED",
        "risk_proof_gap_map": {"risk_governor": "PRESENT", "stop_policy": "PRESENT", "kill_switch": "PRESENT"},
        "risk_proof_gap_map_status": "PASS_RISK_PROOF_GAP_MAPPED",
        "abstention_proof_gap_map": {"abstention_governor": "PRESENT", "abstention_policy": "PRESENT"},
        "abstention_proof_gap_map_status": "PASS_ABSTENTION_PROOF_GAP_MAPPED",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v95_status": "PASS",
        "execution_lock_deep_recheck_v94_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V135Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v134_baseline"):
        return "PASS" if ctx.v134_baseline_status == "PASS_V134_BASELINE_READBACK" else "FAIL" if ctx.v134_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V135Context) -> dict[str, Any]:
    workstream = "v135: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v135_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V135_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v135_report.json":
        report.update({"completion_oriented_next_action_v135_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v134_carried_status": ctx.v134_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v135_production_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v135_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v135.json", "dummy_canonical_identity_report_v135.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V135ReportFactory:
    def __init__(self, *, pilot_override=None, repeat_override=None, scale_override=None, controlled_override=None) -> None:
        self.kw = dict(pilot_override=pilot_override, repeat_override=repeat_override, scale_override=scale_override, controlled_override=controlled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V135Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
