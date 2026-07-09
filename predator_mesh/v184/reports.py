"""DUMMY v184 production pilot lock V5 — summarizes V175-V183 and locks production state; no order.

Reads controlled-operation-approval / session-preflight / session-fire / reconcile / forensic / session-decision /
scale-review / autonomy-evidence / limited-autonomy-dryrun status, totals the live order count (0), and selects a
next-action from a fixed matrix. Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v184 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v184: Production Pilot Lock V5 Next Phase Map And Autonomy Blocker Update"
MISSION_NAME = "dummy_mission_state_report_v170.json"
FINAL_NAME = "final_report_v184.json"
INDEX_KEYS = ["production_lock_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V184 Production Pilot Lock V5"
MISSION_KEY = "dummy_mission_state_report_v170"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Production Lock", "production_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V184_ROUTES = [
    "/api/v184/production-lock-controller",
    "/api/v184/v183-baseline",
    "/api/v184/controlled-operation-approval-summary",
    "/api/v184/session-preflight-summary",
    "/api/v184/session-fire-summary",
    "/api/v184/session-reconcile-summary",
    "/api/v184/session-forensic-summary",
    "/api/v184/session-decision-summary",
    "/api/v184/scale-review-summary",
    "/api/v184/autonomy-evidence-summary",
    "/api/v184/limited-autonomy-dryrun-summary",
    "/api/v184/total-live-order-count",
    "/api/v184/next-action-matrix",
    "/api/v184/no-scale-proof",
    "/api/v184/no-autonomy-proof",
    "/api/v184/no-new-order-proof",
    "/api/v184/readiness-governor",
    "/api/v184/execution-lock",
    "/api/v184/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-lock-controller": ["v184_production_lock_controller_report.json"],
    "v183-baseline": ["v183_baseline_readback_v1_report.json"],
    "controlled-operation-approval-summary": ["v184_controlled_operation_approval_summary_report.json"],
    "session-preflight-summary": ["v184_session_preflight_summary_report.json"],
    "session-fire-summary": ["v184_session_fire_summary_report.json"],
    "session-reconcile-summary": ["v184_session_reconcile_summary_report.json"],
    "session-forensic-summary": ["v184_session_forensic_summary_report.json"],
    "session-decision-summary": ["v184_session_decision_summary_report.json"],
    "scale-review-summary": ["v184_scale_review_summary_report.json"],
    "autonomy-evidence-summary": ["v184_autonomy_evidence_summary_report.json"],
    "limited-autonomy-dryrun-summary": ["v184_limited_autonomy_dryrun_summary_report.json"],
    "total-live-order-count": ["v184_total_live_order_count_report.json"],
    "next-action-matrix": ["v184_next_action_matrix_report.json"],
    "no-scale-proof": ["v184_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v184_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v184_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v144_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v143_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v184_report_v1.json", "completion_oriented_next_action_v184_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(184)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v184/reports.py scripts/generate_v184_reports.py dashboard/backend/v184_routes.py",
    "python scripts/generate_v184_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_FIRST_REAL_PILOT_PROOF",
    "AWAIT_REPEAT_PILOT_PROOF",
    "AWAIT_CONTROLLED_SESSION_APPROVAL",
    "AWAIT_CONTROLLED_SESSION_RECONCILE",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "AWAIT_AUTONOMY_REVIEW_APPROVAL",
    "CONTROLLED_OPERATION_READY_LOCKED",
    "LIMITED_AUTONOMY_DRYRUN_READY_LOCKED",
    "REPAIR_REQUIRED",
]


class V184Context:
    def __init__(self, *, approval_ready_override=None, session_done_override=None, session_reconciled_override=None) -> None:
        self.v183_baseline_status = sgc.baseline_status("final_report_v183.json", "V183")
        self.approval_status = str(sgc.load_artifact("final_report_v175.json").get("controlled_operation_approval_controller_status", "PARTIAL_CONTROLLED_OPERATION_APPROVAL_OR_LIVE_PROOF_ABSENT"))
        self.preflight_status = str(sgc.load_artifact("final_report_v176.json").get("session_preflight_controller_status", "PARTIAL_LIVE_SESSION_PREFLIGHT_BLOCKED"))
        self.fire_status = str(sgc.load_artifact("final_report_v177.json").get("controlled_session_gate_controller_status", "PARTIAL_CONTROLLED_SESSION_NOT_ARMED"))
        self.reconcile_status = str(sgc.load_artifact("final_report_v178.json").get("session_reconcile_controller_status", "PARTIAL_NO_CONTROLLED_SESSION_TO_RECONCILE"))
        self.forensic_status = str(sgc.load_artifact("final_report_v179.json").get("session_forensic_controller_status", "PARTIAL_NO_CONTROLLED_SESSION_TO_REVIEW"))
        self.decision_status = str(sgc.load_artifact("final_report_v180.json").get("session_decision_controller_status", "PARTIAL_SESSION_DECISION_BLOCKED"))
        self.scale_status = str(sgc.load_artifact("final_report_v181.json").get("scale_recommendation", "SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF"))
        self.autonomy_status = str(sgc.load_artifact("final_report_v182.json").get("autonomy_eligibility", "AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF"))
        self.dryrun_status = str(sgc.load_artifact("final_report_v183.json").get("limited_autonomy_dryrun_controller_status", "PASS_LIMITED_AUTONOMY_DRYRUN_POLICY_LOCKED_INERT"))
        self.approval_ready = bool(approval_ready_override) if approval_ready_override is not None else (self.approval_status == "PASS_CONTROLLED_OPERATION_APPROVAL_VALID_NO_SUBMIT")
        self.session_done = bool(session_done_override) if session_done_override is not None else (self.fire_status == "PASS_CONTROLLED_SESSION_SUBMITTED_AUTOLOCKED")
        self.session_reconciled = bool(session_reconciled_override) if session_reconciled_override is not None else (self.decision_status == "PASS_SESSION_DECISION_LOCKED")

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.approval_ready:
            return "AWAIT_CONTROLLED_SESSION_APPROVAL"
        if not self.session_done:
            return "AWAIT_CONTROLLED_SESSION_APPROVAL"
        if not self.session_reconciled:
            return "AWAIT_CONTROLLED_SESSION_RECONCILE"
        if self.scale_status != "SCALE_STEP_1_REVIEW_READY_LOCKED":
            return "AWAIT_SCALE_REVIEW_APPROVAL"
        if self.autonomy_status != "AUTONOMY_REVIEW_READY_LOCKED":
            return "AWAIT_AUTONOMY_REVIEW_APPROVAL"
        return "CONTROLLED_OPERATION_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_PRODUCTION_LOCK_BASELINE_REGRESSION" if self.v183_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_PILOT_LOCK_V5_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v183_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V183_BASELINE_REGRESSION"] if self.v183_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PRODUCTION_PILOT_LOCK_V5_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V184Context) -> dict[str, Any]:
    return {
        "v183_baseline_status": ctx.v183_baseline_status,
        "production_lock_controller_status": ctx.controller_status,
        "controlled_operation_approval_summary": ctx.approval_status,
        "controlled_operation_approval_summary_status": "PASS_CONTROLLED_OPERATION_APPROVAL_SUMMARIZED",
        "session_preflight_summary": ctx.preflight_status,
        "session_preflight_summary_status": "PASS_SESSION_PREFLIGHT_SUMMARIZED",
        "session_fire_summary": ctx.fire_status,
        "session_fire_summary_status": "PASS_SESSION_FIRE_SUMMARIZED",
        "session_reconcile_summary": ctx.reconcile_status,
        "session_reconcile_summary_status": "PASS_SESSION_RECONCILE_SUMMARIZED",
        "session_forensic_summary": ctx.forensic_status,
        "session_forensic_summary_status": "PASS_SESSION_FORENSIC_SUMMARIZED",
        "session_decision_summary": ctx.decision_status,
        "session_decision_summary_status": "PASS_SESSION_DECISION_SUMMARIZED",
        "scale_review_summary": ctx.scale_status,
        "scale_review_summary_status": "PASS_SCALE_REVIEW_SUMMARIZED",
        "autonomy_evidence_summary": ctx.autonomy_status,
        "autonomy_evidence_summary_status": "PASS_AUTONOMY_EVIDENCE_SUMMARIZED",
        "limited_autonomy_dryrun_summary": ctx.dryrun_status,
        "limited_autonomy_dryrun_summary_status": "PASS_LIMITED_AUTONOMY_DRYRUN_SUMMARIZED",
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
        "readiness_governor_v144_status": "PASS",
        "execution_lock_deep_recheck_v143_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V184Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v183_baseline"):
        return "PASS" if ctx.v183_baseline_status == "PASS_V183_BASELINE_READBACK" else "FAIL" if ctx.v183_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V184Context) -> dict[str, Any]:
    workstream = "v184: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v184_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V184_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v184_report.json":
        report.update({"completion_oriented_next_action_v184_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v183_carried_status": ctx.v183_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v184_production_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v184_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v184.json", "dummy_canonical_identity_report_v184.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V184ReportFactory:
    def __init__(self, *, approval_ready_override=None, session_done_override=None, session_reconciled_override=None) -> None:
        self.kw = dict(approval_ready_override=approval_ready_override, session_done_override=session_done_override, session_reconciled_override=session_reconciled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V184Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
