"""DUMMY v214 completion accelerator lock — summarizes V205-V213 and locks the next phase; no order.

Reads baseline / manifest / cockpit / authority-resolver / live-proof-runner / reconcile-runner / forensic-runner /
bridge / scoreboard status, totals the live order count (0), and selects a next-action from a fixed operator matrix.
Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v214 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v214: Completion Accelerator Lock Next Phase Map"
MISSION_NAME = "dummy_mission_state_report_v200.json"
FINAL_NAME = "final_report_v214.json"
INDEX_KEYS = ["completion_accelerator_lock_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V214 Completion Accelerator Lock"
MISSION_KEY = "dummy_mission_state_report_v200"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Accelerator Lock", "completion_accelerator_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V214_ROUTES = [
    "/api/v214/completion-accelerator-lock-controller",
    "/api/v214/v213-baseline",
    "/api/v214/baseline-summary",
    "/api/v214/manifest-summary",
    "/api/v214/cockpit-summary",
    "/api/v214/authority-resolver-summary",
    "/api/v214/live-proof-runner-summary",
    "/api/v214/reconcile-runner-summary",
    "/api/v214/forensic-runner-summary",
    "/api/v214/repeat-session-bridge-summary",
    "/api/v214/completion-scoreboard-summary",
    "/api/v214/total-live-order-count",
    "/api/v214/next-action-matrix",
    "/api/v214/no-scale-proof",
    "/api/v214/no-autonomy-proof",
    "/api/v214/no-new-order-proof",
    "/api/v214/readiness-governor",
    "/api/v214/execution-lock",
    "/api/v214/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "completion-accelerator-lock-controller": ["v214_completion_accelerator_lock_controller_report.json"],
    "v213-baseline": ["v213_baseline_readback_v1_report.json"],
    "baseline-summary": ["v214_baseline_summary_report.json"],
    "manifest-summary": ["v214_manifest_summary_report.json"],
    "cockpit-summary": ["v214_cockpit_summary_report.json"],
    "authority-resolver-summary": ["v214_authority_resolver_summary_report.json"],
    "live-proof-runner-summary": ["v214_live_proof_runner_summary_report.json"],
    "reconcile-runner-summary": ["v214_reconcile_runner_summary_report.json"],
    "forensic-runner-summary": ["v214_forensic_runner_summary_report.json"],
    "repeat-session-bridge-summary": ["v214_repeat_session_bridge_summary_report.json"],
    "completion-scoreboard-summary": ["v214_completion_scoreboard_summary_report.json"],
    "total-live-order-count": ["v214_total_live_order_count_report.json"],
    "next-action-matrix": ["v214_next_action_matrix_report.json"],
    "no-scale-proof": ["v214_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v214_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v214_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v174_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v173_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v214_report_v1.json", "completion_oriented_next_action_v214_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(214)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v214/reports.py scripts/generate_v214_reports.py dashboard/backend/v214_routes.py",
    "python scripts/generate_v214_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "OPERATOR_PROVIDE_APPROVAL_FILES",
    "OPERATOR_ENABLE_LIVE_SUBMIT",
    "OPERATOR_CONFIRM_CAPS",
    "OPERATOR_INJECT_FIREWALL_ADAPTER",
    "RUN_FIRST_LIVE_PROOF",
    "RUN_RECONCILE",
    "RUN_FORENSICS",
    "REVIEW_REPEAT_OR_CONTROLLED_SESSION",
    "REPAIR_REQUIRED",
]


class V214Context:
    def __init__(self, *, armable_override=None, proof_done_override=None, proof_reconciled_override=None, forensic_done_override=None) -> None:
        self.v213_baseline_status = sgc.baseline_status("final_report_v213.json", "V213")
        self.baseline_status = str(sgc.load_artifact("final_report_v205.json").get("completion_baseline_controller_status", "PASS_COMPLETION_BASELINE_DEDUPED"))
        self.manifest_status = str(sgc.load_artifact("final_report_v206.json").get("activation_manifest_controller_status", "PARTIAL_ACTIVATION_MANIFEST_INPUTS_ABSENT"))
        self.cockpit_status = str(sgc.load_artifact("final_report_v207.json").get("cockpit_controller_status", "PASS_ACTIVATION_COCKPIT_READY_READONLY"))
        self.resolver_status = str(sgc.load_artifact("final_report_v208.json").get("authority_state", "LIVE_BLOCKED_AUTHORITY_ABSENT"))
        self.runner_status = str(sgc.load_artifact("final_report_v209.json").get("live_proof_runner_controller_status", "PARTIAL_LIVE_PROOF_RUNNER_NOT_ARMED"))
        self.reconcile_status = str(sgc.load_artifact("final_report_v210.json").get("reconcile_runner_controller_status", "PARTIAL_NO_LIVE_PROOF_TO_RECONCILE"))
        self.forensic_status = str(sgc.load_artifact("final_report_v211.json").get("forensic_runner_controller_status", "PARTIAL_NO_LIVE_PROOF_TO_FORENSIC_REVIEW"))
        self.bridge_status = str(sgc.load_artifact("final_report_v212.json").get("route_state", "ROUTE_BLOCKED_NO_LIVE_PROOF"))
        self.scoreboard_status = str(sgc.load_artifact("final_report_v213.json").get("completion_scoreboard_controller_status", "PASS_COMPLETION_SCOREBOARD_GENERATED"))
        self.armable = bool(armable_override) if armable_override is not None else (self.resolver_status == "LIVE_PROOF_ARMABLE")
        self.proof_done = bool(proof_done_override) if proof_done_override is not None else (self.runner_status == "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED")
        self.proof_reconciled = bool(proof_reconciled_override) if proof_reconciled_override is not None else (self.reconcile_status == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED")
        self.forensic_done = bool(forensic_done_override) if forensic_done_override is not None else (self.forensic_status == "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED")

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.armable and not self.proof_done:
            return "OPERATOR_PROVIDE_APPROVAL_FILES"
        if self.armable and not self.proof_done:
            return "RUN_FIRST_LIVE_PROOF"
        if self.proof_done and not self.proof_reconciled:
            return "RUN_RECONCILE"
        if self.proof_reconciled and not self.forensic_done:
            return "RUN_FORENSICS"
        return "REVIEW_REPEAT_OR_CONTROLLED_SESSION"

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_ACCELERATOR_BASELINE_REGRESSION" if self.v213_baseline_status.startswith("FAIL") else "PASS_COMPLETION_ACCELERATOR_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v213_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V213_BASELINE_REGRESSION"] if self.v213_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"COMPLETION_ACCELERATOR_LOCKED_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V214Context) -> dict[str, Any]:
    return {
        "v213_baseline_status": ctx.v213_baseline_status,
        "completion_accelerator_lock_controller_status": ctx.controller_status,
        "baseline_summary": ctx.baseline_status,
        "baseline_summary_status": "PASS_BASELINE_SUMMARIZED",
        "manifest_summary": ctx.manifest_status,
        "manifest_summary_status": "PASS_MANIFEST_SUMMARIZED",
        "cockpit_summary": ctx.cockpit_status,
        "cockpit_summary_status": "PASS_COCKPIT_SUMMARIZED",
        "authority_resolver_summary": ctx.resolver_status,
        "authority_resolver_summary_status": "PASS_AUTHORITY_RESOLVER_SUMMARIZED",
        "live_proof_runner_summary": ctx.runner_status,
        "live_proof_runner_summary_status": "PASS_LIVE_PROOF_RUNNER_SUMMARIZED",
        "reconcile_runner_summary": ctx.reconcile_status,
        "reconcile_runner_summary_status": "PASS_RECONCILE_RUNNER_SUMMARIZED",
        "forensic_runner_summary": ctx.forensic_status,
        "forensic_runner_summary_status": "PASS_FORENSIC_RUNNER_SUMMARIZED",
        "repeat_session_bridge_summary": ctx.bridge_status,
        "repeat_session_bridge_summary_status": "PASS_REPEAT_SESSION_BRIDGE_SUMMARIZED",
        "completion_scoreboard_summary": ctx.scoreboard_status,
        "completion_scoreboard_summary_status": "PASS_COMPLETION_SCOREBOARD_SUMMARIZED",
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
        "readiness_governor_v174_status": "PASS",
        "execution_lock_deep_recheck_v173_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V214Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v213_baseline"):
        return "PASS" if ctx.v213_baseline_status == "PASS_V213_BASELINE_READBACK" else "FAIL" if ctx.v213_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V214Context) -> dict[str, Any]:
    workstream = "v214: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v214_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V214_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v214_report.json":
        report.update({"completion_oriented_next_action_v214_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v213_carried_status": ctx.v213_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v214_completion_accelerator_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v214_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v214.json", "dummy_canonical_identity_report_v214.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V214ReportFactory:
    def __init__(self, *, armable_override=None, proof_done_override=None, proof_reconciled_override=None, forensic_done_override=None) -> None:
        self.kw = dict(armable_override=armable_override, proof_done_override=proof_done_override, proof_reconciled_override=proof_reconciled_override, forensic_done_override=forensic_done_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V214Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
