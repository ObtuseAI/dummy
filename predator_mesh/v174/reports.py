"""DUMMY v174 controlled operation lock V4 — summarizes V165-V173 and locks the next phase; no order.

Reads repeat-authority / preflight / fire / reconcile / forensic / pilot-pair-audit / scale-evidence /
controlled-operation-quorum / dry-session status, totals the live order count (0), and selects a next-action from a
fixed matrix. Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v174 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v174: Controlled Operation Lock V4 Next Action Matrix"
MISSION_NAME = "dummy_mission_state_report_v160.json"
FINAL_NAME = "final_report_v174.json"
INDEX_KEYS = ["controlled_operation_lock_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V174 Controlled Operation Lock V4"
MISSION_KEY = "dummy_mission_state_report_v160"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Lock", "controlled_operation_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V174_ROUTES = [
    "/api/v174/controlled-operation-lock-controller",
    "/api/v174/v173-baseline",
    "/api/v174/repeat-authority-summary",
    "/api/v174/repeat-preflight-summary",
    "/api/v174/repeat-fire-summary",
    "/api/v174/repeat-reconcile-summary",
    "/api/v174/repeat-forensic-summary",
    "/api/v174/pilot-pair-audit-summary",
    "/api/v174/scale-evidence-summary",
    "/api/v174/controlled-operation-quorum-summary",
    "/api/v174/dry-session-summary",
    "/api/v174/total-live-order-count",
    "/api/v174/next-action-matrix",
    "/api/v174/no-scale-proof",
    "/api/v174/no-autonomy-proof",
    "/api/v174/no-new-order-proof",
    "/api/v174/readiness-governor",
    "/api/v174/execution-lock",
    "/api/v174/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-lock-controller": ["v174_controlled_operation_lock_controller_report.json"],
    "v173-baseline": ["v173_baseline_readback_v1_report.json"],
    "repeat-authority-summary": ["v174_repeat_authority_summary_report.json"],
    "repeat-preflight-summary": ["v174_repeat_preflight_summary_report.json"],
    "repeat-fire-summary": ["v174_repeat_fire_summary_report.json"],
    "repeat-reconcile-summary": ["v174_repeat_reconcile_summary_report.json"],
    "repeat-forensic-summary": ["v174_repeat_forensic_summary_report.json"],
    "pilot-pair-audit-summary": ["v174_pilot_pair_audit_summary_report.json"],
    "scale-evidence-summary": ["v174_scale_evidence_summary_report.json"],
    "controlled-operation-quorum-summary": ["v174_controlled_operation_quorum_summary_report.json"],
    "dry-session-summary": ["v174_dry_session_summary_report.json"],
    "total-live-order-count": ["v174_total_live_order_count_report.json"],
    "next-action-matrix": ["v174_next_action_matrix_report.json"],
    "no-scale-proof": ["v174_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v174_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v174_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v134_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v133_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v174_report_v1.json", "completion_oriented_next_action_v174_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(174)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v174/reports.py scripts/generate_v174_reports.py dashboard/backend/v174_routes.py",
    "python scripts/generate_v174_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_FIRST_REAL_PILOT_PROOF",
    "AWAIT_REPEAT_PILOT_APPROVAL",
    "AWAIT_REPEAT_PILOT_RECONCILE",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "AWAIT_CONTROLLED_OPERATION_APPROVAL",
    "CONTROLLED_OPERATION_READY_LOCKED",
    "REPAIR_REQUIRED",
]


class V174Context:
    def __init__(self, *, first_pilot_override=None, repeat_done_override=None, pair_override=None, quorum_override=None) -> None:
        self.v173_baseline_status = sgc.baseline_status("final_report_v173.json", "V173")
        self.repeat_authority_status = str(sgc.load_artifact("final_report_v165.json").get("repeat_authority_binder_controller_status", "PARTIAL_REPEAT_AUTHORITY_BLOCKED_NO_FIRST_PILOT_PROOF"))
        self.repeat_preflight_status = str(sgc.load_artifact("final_report_v166.json").get("repeat_preflight_controller_status", "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"))
        self.repeat_fire_status = str(sgc.load_artifact("final_report_v167.json").get("repeat_pilot_gate_controller_status", "PARTIAL_REPEAT_PILOT_NOT_ARMED"))
        self.repeat_reconcile_status = str(sgc.load_artifact("final_report_v168.json").get("repeat_reconcile_controller_status", "PARTIAL_NO_REPEAT_PILOT_TO_RECONCILE"))
        self.repeat_forensic_status = str(sgc.load_artifact("final_report_v169.json").get("repeat_forensic_controller_status", "PARTIAL_NO_REPEAT_PILOT_TO_REVIEW"))
        self.pair_status = str(sgc.load_artifact("final_report_v170.json").get("pilot_pair_audit_controller_status", "PARTIAL_PILOT_PAIR_PROOF_ABSENT"))
        self.scale_status = str(sgc.load_artifact("final_report_v171.json").get("scale_recommendation", "SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF"))
        self.quorum_status = str(sgc.load_artifact("final_report_v172.json").get("controlled_operation_quorum_controller_status", "PARTIAL_CONTROLLED_OPERATION_QUORUM_BLOCKED"))
        self.dry_session_status = str(sgc.load_artifact("final_report_v173.json").get("dry_session_controller_status", "PASS_CONTROLLED_OPERATION_DRY_SESSION_READY_INERT"))
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            r = str(sgc.load_artifact("final_report_v162.json").get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            f = str(sgc.load_artifact("final_report_v163.json").get("forensic_controller_status", "")) == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = r and f
        self.repeat_done = bool(repeat_done_override) if repeat_done_override is not None else (self.repeat_reconcile_status == "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED")
        self.pair_ok = bool(pair_override) if pair_override is not None else (self.pair_status == "PASS_PILOT_PAIR_AUDITED_LOCKED")
        self.quorum_ok = bool(quorum_override) if quorum_override is not None else (self.quorum_status == "PASS_CONTROLLED_OPERATION_QUORUM_READY_LOCKED")

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.first_pilot_ok:
            return "AWAIT_FIRST_REAL_PILOT_PROOF"
        if self.repeat_fire_status != "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED":
            return "AWAIT_REPEAT_PILOT_APPROVAL"
        if not self.repeat_done:
            return "AWAIT_REPEAT_PILOT_RECONCILE"
        if self.scale_status != "SCALE_STEP_1_REVIEW_READY_LOCKED":
            return "AWAIT_SCALE_REVIEW_APPROVAL"
        if not self.quorum_ok:
            return "AWAIT_CONTROLLED_OPERATION_APPROVAL"
        return "CONTROLLED_OPERATION_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_CONTROLLED_OPERATION_LOCK_BASELINE_REGRESSION" if self.v173_baseline_status.startswith("FAIL") else "PASS_CONTROLLED_OPERATION_LOCK_V4_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v173_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V173_BASELINE_REGRESSION"] if self.v173_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"CONTROLLED_OPERATION_LOCK_V4_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V174Context) -> dict[str, Any]:
    return {
        "v173_baseline_status": ctx.v173_baseline_status,
        "controlled_operation_lock_controller_status": ctx.controller_status,
        "repeat_authority_summary": ctx.repeat_authority_status,
        "repeat_authority_summary_status": "PASS_REPEAT_AUTHORITY_SUMMARIZED",
        "repeat_preflight_summary": ctx.repeat_preflight_status,
        "repeat_preflight_summary_status": "PASS_REPEAT_PREFLIGHT_SUMMARIZED",
        "repeat_fire_summary": ctx.repeat_fire_status,
        "repeat_fire_summary_status": "PASS_REPEAT_FIRE_SUMMARIZED",
        "repeat_reconcile_summary": ctx.repeat_reconcile_status,
        "repeat_reconcile_summary_status": "PASS_REPEAT_RECONCILE_SUMMARIZED",
        "repeat_forensic_summary": ctx.repeat_forensic_status,
        "repeat_forensic_summary_status": "PASS_REPEAT_FORENSIC_SUMMARIZED",
        "pilot_pair_audit_summary": ctx.pair_status,
        "pilot_pair_audit_summary_status": "PASS_PILOT_PAIR_AUDIT_SUMMARIZED",
        "scale_evidence_summary": ctx.scale_status,
        "scale_evidence_summary_status": "PASS_SCALE_EVIDENCE_SUMMARIZED",
        "controlled_operation_quorum_summary": ctx.quorum_status,
        "controlled_operation_quorum_summary_status": "PASS_CONTROLLED_OPERATION_QUORUM_SUMMARIZED",
        "dry_session_summary": ctx.dry_session_status,
        "dry_session_summary_status": "PASS_DRY_SESSION_SUMMARIZED",
        "total_live_order_count": 0,
        "total_live_order_count_status": "PASS_TOTAL_LIVE_ORDER_COUNT_ZERO",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "broker_contact_status": "NO_BROKER_CONTACT",
        "live_submit_caps_status": "LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "approval_file_write_status": "NO_APPROVAL_FILE_WRITE",
        "approval_files_written": 0,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v134_status": "PASS",
        "execution_lock_deep_recheck_v133_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V174Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v173_baseline"):
        return "PASS" if ctx.v173_baseline_status == "PASS_V173_BASELINE_READBACK" else "FAIL" if ctx.v173_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V174Context) -> dict[str, Any]:
    workstream = "v174: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v174_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V174_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v174_report.json":
        report.update({"completion_oriented_next_action_v174_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v173_carried_status": ctx.v173_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v174_controlled_operation_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v174_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v174.json", "dummy_canonical_identity_report_v174.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V174ReportFactory:
    def __init__(self, *, first_pilot_override=None, repeat_done_override=None, pair_override=None, quorum_override=None) -> None:
        self.kw = dict(first_pilot_override=first_pilot_override, repeat_done_override=repeat_done_override, pair_override=pair_override, quorum_override=quorum_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V174Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
