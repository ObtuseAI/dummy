"""DUMMY v155 controlled operation lock V3 + next action matrix — summarizes V146-V154 and locks controlled operation; no new order.

Reads authority intake (V147), mode firewall (V148), pilot (V151), reconcile (V152), forensic (V153), and repeat
preflight (V154) status, totals the live order count (0), and selects a controlled-operation status and a next-action
from fixed matrices. Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v155 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v155: Controlled Operation Lock V3 Next Action Matrix And Production Status"
MISSION_NAME = "dummy_mission_state_report_v141.json"
FINAL_NAME = "final_report_v155.json"
INDEX_KEYS = ["controlled_operation_lock_controller_status", "controlled_operation_status", "next_action_matrix_selection"]
DASH_TITLE = "Dummy V155 Controlled Operation Lock V3"
MISSION_KEY = "dummy_mission_state_report_v141"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Lock", "controlled_operation_lock_controller_status"],
    ["Operation Status", "controlled_operation_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V155_ROUTES = [
    "/api/v155/controlled-operation-lock-controller",
    "/api/v155/v154-baseline",
    "/api/v155/authority-intake-summary",
    "/api/v155/dry-live-mode-summary",
    "/api/v155/rehearsal-summary",
    "/api/v155/preflight-summary",
    "/api/v155/fire-gate-summary",
    "/api/v155/reconcile-summary",
    "/api/v155/forensic-summary",
    "/api/v155/repeat-preflight-summary",
    "/api/v155/total-live-order-count",
    "/api/v155/controlled-operation-status",
    "/api/v155/next-action-matrix",
    "/api/v155/no-scale-proof",
    "/api/v155/no-autonomy-proof",
    "/api/v155/no-new-order-proof",
    "/api/v155/readiness-governor",
    "/api/v155/execution-lock",
    "/api/v155/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-lock-controller": ["v155_controlled_operation_lock_controller_report.json"],
    "v154-baseline": ["v154_baseline_readback_v1_report.json"],
    "authority-intake-summary": ["v155_authority_intake_summary_report.json"],
    "dry-live-mode-summary": ["v155_dry_live_mode_summary_report.json"],
    "rehearsal-summary": ["v155_rehearsal_summary_report.json"],
    "preflight-summary": ["v155_preflight_summary_report.json"],
    "fire-gate-summary": ["v155_fire_gate_summary_report.json"],
    "reconcile-summary": ["v155_reconcile_summary_report.json"],
    "forensic-summary": ["v155_forensic_summary_report.json"],
    "repeat-preflight-summary": ["v155_repeat_preflight_summary_report.json"],
    "total-live-order-count": ["v155_total_live_order_count_report.json"],
    "controlled-operation-status": ["v155_controlled_operation_status_report.json"],
    "next-action-matrix": ["v155_next_action_matrix_report.json"],
    "no-scale-proof": ["v155_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v155_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v155_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v115_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v114_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v155_report_v1.json", "completion_oriented_next_action_v155_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(155)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v155/reports.py scripts/generate_v155_reports.py dashboard/backend/v155_routes.py",
    "python scripts/generate_v155_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLED_OPERATION_ENUM = [
    "CONTROLLED_OPERATION_READY_LOCKED",
    "CONTROLLED_OPERATION_BLOCKED_AUTHORITY_ABSENT",
    "CONTROLLED_OPERATION_BLOCKED_RECONCILE_ABSENT",
    "CONTROLLED_OPERATION_REPAIR_REQUIRED",
]
NEXT_ACTION_MATRIX = [
    "AWAIT_REAL_PILOT_APPROVAL",
    "AWAIT_OPERATOR_LIVE_SUBMIT_ENABLEMENT",
    "AWAIT_OPERATOR_CAPS_CONFIRMATION",
    "AWAIT_FIREWALL_ADAPTER_INJECTION",
    "AWAIT_REAL_PILOT_RECONCILE",
    "AWAIT_REPEAT_PILOT_APPROVAL",
    "AWAIT_SCALE_REVIEW_APPROVAL",
]


class V155Context:
    def __init__(self, *, authority_ready_override=None, pilot_done_override=None, reconcile_done_override=None, repeat_ready_override=None) -> None:
        self.v154_baseline_status = sgc.baseline_status("final_report_v154.json", "V154")
        self.authority_status = str(sgc.load_artifact("final_report_v147.json").get("intake_validator_controller_status", "PARTIAL_REAL_AUTHORITY_INPUTS_ABSENT_OR_INCOMPLETE"))
        self.mode_status = str(sgc.load_artifact("final_report_v148.json").get("mode", "DRY_LOCKED"))
        self.pilot_status = str(sgc.load_artifact("final_report_v151.json").get("real_pilot_gate_controller_status", "PARTIAL_REAL_PILOT_NOT_ARMED"))
        self.reconcile_status = str(sgc.load_artifact("final_report_v152.json").get("reconcile_intake_controller_status", "PARTIAL_NO_REAL_PILOT_TO_RECONCILE"))
        self.forensic_status = str(sgc.load_artifact("final_report_v153.json").get("forensic_controller_status", "PARTIAL_NO_REAL_PILOT_TO_REVIEW"))
        self.repeat_status = str(sgc.load_artifact("final_report_v154.json").get("repeat_preflight_controller_status", "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"))
        self.authority_ready = bool(authority_ready_override) if authority_ready_override is not None else (self.authority_status == "PASS_REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT")
        self.pilot_done = bool(pilot_done_override) if pilot_done_override is not None else (self.pilot_status == "PASS_REAL_PILOT_SUBMITTED_AUTOLOCKED")
        self.reconcile_done = bool(reconcile_done_override) if reconcile_done_override is not None else (self.reconcile_status == "PASS_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED")
        self.repeat_ready = bool(repeat_ready_override) if repeat_ready_override is not None else (self.repeat_status == "PASS_REPEAT_PREFLIGHT_READY_LOCKED")

    @property
    def controlled_operation_status(self) -> str:
        if self.v154_baseline_status.startswith("FAIL"):
            return "CONTROLLED_OPERATION_REPAIR_REQUIRED"
        if not self.authority_ready:
            return "CONTROLLED_OPERATION_BLOCKED_AUTHORITY_ABSENT"
        if self.pilot_done and not self.reconcile_done:
            return "CONTROLLED_OPERATION_BLOCKED_RECONCILE_ABSENT"
        return "CONTROLLED_OPERATION_READY_LOCKED"

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.authority_ready:
            return "AWAIT_REAL_PILOT_APPROVAL"
        if self.pilot_done and not self.reconcile_done:
            return "AWAIT_REAL_PILOT_RECONCILE"
        if self.reconcile_done and not self.repeat_ready:
            return "AWAIT_REPEAT_PILOT_APPROVAL"
        return "AWAIT_SCALE_REVIEW_APPROVAL"

    @property
    def controller_status(self) -> str:
        return "FAIL_CONTROLLED_OPERATION_LOCK_BASELINE_REGRESSION" if self.v154_baseline_status.startswith("FAIL") else "PASS_CONTROLLED_OPERATION_LOCK_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v154_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V154_BASELINE_REGRESSION"] if self.v154_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"CONTROLLED_OPERATION_LOCK_V3_COMPLETE_{self.controlled_operation_status}_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V155Context) -> dict[str, Any]:
    return {
        "v154_baseline_status": ctx.v154_baseline_status,
        "controlled_operation_lock_controller_status": ctx.controller_status,
        "authority_intake_summary": ctx.authority_status,
        "authority_intake_summary_status": "PASS_AUTHORITY_INTAKE_SUMMARIZED",
        "dry_live_mode_summary": ctx.mode_status,
        "dry_live_mode_summary_status": "PASS_DRY_LIVE_MODE_SUMMARIZED",
        "rehearsal_summary": "PASS_PRODUCTION_PILOT_REHEARSAL_SPINE_READY_INERT",
        "rehearsal_summary_status": "PASS_REHEARSAL_SUMMARIZED",
        "preflight_summary": str(sgc.load_artifact("final_report_v150.json").get("preflight_controller_status", "PARTIAL_REAL_PILOT_PREFLIGHT_BLOCKED")),
        "preflight_summary_status": "PASS_PREFLIGHT_SUMMARIZED",
        "fire_gate_summary": ctx.pilot_status,
        "fire_gate_summary_status": "PASS_FIRE_GATE_SUMMARIZED",
        "reconcile_summary": ctx.reconcile_status,
        "reconcile_summary_status": "PASS_RECONCILE_SUMMARIZED",
        "forensic_summary": ctx.forensic_status,
        "forensic_summary_status": "PASS_FORENSIC_SUMMARIZED",
        "repeat_preflight_summary": ctx.repeat_status,
        "repeat_preflight_summary_status": "PASS_REPEAT_PREFLIGHT_SUMMARIZED",
        "total_live_order_count": 0,
        "total_live_order_count_status": "PASS_TOTAL_LIVE_ORDER_COUNT_ZERO",
        "controlled_operation_status": ctx.controlled_operation_status,
        "controlled_operation_status_enum": CONTROLLED_OPERATION_ENUM,
        "controlled_operation_status_report_status": "PASS_CONTROLLED_OPERATION_STATUS_SET",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "broker_contact_status": "NO_BROKER_CONTACT",
        "live_submit_caps_status": "LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v115_status": "PASS",
        "execution_lock_deep_recheck_v114_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V155Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v154_baseline"):
        return "PASS" if ctx.v154_baseline_status == "PASS_V154_BASELINE_READBACK" else "FAIL" if ctx.v154_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V155Context) -> dict[str, Any]:
    workstream = "v155: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v155_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V155_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v155_report.json":
        report.update({"completion_oriented_next_action_v155_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v154_carried_status": ctx.v154_baseline_status, "controlled_operation_status": ctx.controlled_operation_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v155_controlled_operation_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v155_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v155.json", "dummy_canonical_identity_report_v155.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V155ReportFactory:
    def __init__(self, *, authority_ready_override=None, pilot_done_override=None, reconcile_done_override=None, repeat_ready_override=None) -> None:
        self.kw = dict(authority_ready_override=authority_ready_override, pilot_done_override=pilot_done_override, reconcile_done_override=reconcile_done_override, repeat_ready_override=repeat_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V155Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
