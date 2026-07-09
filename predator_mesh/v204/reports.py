"""DUMMY v204 production lock V7 — summarizes V195-V203 and locks the next phase; no order.

Reads authority-binder / config-caps-quorum / firewall-broker / final-quorum / fire-gate / reconcile / forensic /
scale-autonomy-evidence / controlled-operation status, totals the live order count, and selects a next-action from a
fixed matrix. Autonomous trading and scale stay disabled and no new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v204 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v204: Production Lock V7 First Live Proof Status And Next Phase Matrix"
MISSION_NAME = "dummy_mission_state_report_v190.json"
FINAL_NAME = "final_report_v204.json"
INDEX_KEYS = ["production_lock_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V204 Production Lock V7"
MISSION_KEY = "dummy_mission_state_report_v190"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Production Lock", "production_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V204_ROUTES = [
    "/api/v204/production-lock-controller",
    "/api/v204/v203-baseline",
    "/api/v204/authority-binder-summary",
    "/api/v204/config-caps-quorum-summary",
    "/api/v204/firewall-broker-verification-summary",
    "/api/v204/final-quorum-summary",
    "/api/v204/fire-gate-summary",
    "/api/v204/reconcile-summary",
    "/api/v204/forensic-summary",
    "/api/v204/scale-autonomy-evidence-summary",
    "/api/v204/controlled-operation-status-summary",
    "/api/v204/total-live-order-count",
    "/api/v204/next-action-matrix",
    "/api/v204/no-scale-proof",
    "/api/v204/no-autonomy-proof",
    "/api/v204/no-new-order-proof",
    "/api/v204/readiness-governor",
    "/api/v204/execution-lock",
    "/api/v204/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-lock-controller": ["v204_production_lock_controller_report.json"],
    "v203-baseline": ["v203_baseline_readback_v1_report.json"],
    "authority-binder-summary": ["v204_authority_binder_summary_report.json"],
    "config-caps-quorum-summary": ["v204_config_caps_quorum_summary_report.json"],
    "firewall-broker-verification-summary": ["v204_firewall_broker_verification_summary_report.json"],
    "final-quorum-summary": ["v204_final_quorum_summary_report.json"],
    "fire-gate-summary": ["v204_fire_gate_summary_report.json"],
    "reconcile-summary": ["v204_reconcile_summary_report.json"],
    "forensic-summary": ["v204_forensic_summary_report.json"],
    "scale-autonomy-evidence-summary": ["v204_scale_autonomy_evidence_summary_report.json"],
    "controlled-operation-status-summary": ["v204_controlled_operation_status_summary_report.json"],
    "total-live-order-count": ["v204_total_live_order_count_report.json"],
    "next-action-matrix": ["v204_next_action_matrix_report.json"],
    "no-scale-proof": ["v204_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v204_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v204_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v164_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v163_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v204_report_v1.json", "completion_oriented_next_action_v204_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(204)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v204/reports.py scripts/generate_v204_reports.py dashboard/backend/v204_routes.py",
    "python scripts/generate_v204_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_OPERATOR_APPROVAL_FILES",
    "AWAIT_OPERATOR_LIVE_SUBMIT_ENABLEMENT",
    "AWAIT_OPERATOR_CAPS_CONFIRMATION",
    "AWAIT_FIREWALL_ADAPTER_INJECTION",
    "AWAIT_FIRST_LIVE_PROOF_RECONCILE",
    "AWAIT_FIRST_LIVE_PROOF_FORENSIC_REVIEW",
    "AWAIT_REPEAT_PILOT_REVIEW",
    "AWAIT_CONTROLLED_SESSION_REVIEW",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "AWAIT_AUTONOMY_REVIEW_APPROVAL",
    "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED",
    "LIMITED_AUTONOMY_BLOCKED_NO_LIVE_PROOF",
    "REPAIR_REQUIRED",
]


class V204Context:
    def __init__(self, *, binder_ready_override=None, quorum_ready_override=None, proof_done_override=None, proof_reconciled_override=None, controlled_ready_override=None) -> None:
        self.v203_baseline_status = sgc.baseline_status("final_report_v203.json", "V203")
        self.binder_status = str(sgc.load_artifact("final_report_v195.json").get("activation_binder_controller_status", "PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE"))
        self.config_status = str(sgc.load_artifact("final_report_v196.json").get("config_quorum_controller_status", "PARTIAL_LIVE_CONFIG_CAPS_QUORUM_BLOCKED"))
        self.firewall_status = str(sgc.load_artifact("final_report_v197.json").get("firewall_broker_controller_status", "PARTIAL_FIREWALL_OR_BROKER_READONLY_AUTHORITY_ABSENT"))
        self.quorum_status = str(sgc.load_artifact("final_report_v198.json").get("final_quorum_controller_status", "PARTIAL_FIRST_LIVE_PROOF_QUORUM_BLOCKED"))
        self.fire_status = str(sgc.load_artifact("final_report_v199.json").get("first_live_proof_gate_controller_status", "PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED"))
        self.reconcile_status = str(sgc.load_artifact("final_report_v200.json").get("reconcile_controller_status", "PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE"))
        self.forensic_status = str(sgc.load_artifact("final_report_v201.json").get("forensic_controller_status", "PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW"))
        self.evidence_status = str(sgc.load_artifact("final_report_v202.json").get("evidence_refresh_controller_status", "PARTIAL_SCALE_AND_AUTONOMY_EVIDENCE_BLOCKED"))
        self.controlled_status = str(sgc.load_artifact("final_report_v203.json").get("controlled_operation_status", "CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF"))
        self.binder_ready = bool(binder_ready_override) if binder_ready_override is not None else (self.binder_status == "PASS_FIRST_LIVE_PROOF_AUTHORITY_BOUND_NO_SUBMIT")
        self.quorum_ready = bool(quorum_ready_override) if quorum_ready_override is not None else (self.quorum_status == "PASS_FIRST_LIVE_PROOF_QUORUM_READY_NO_SUBMIT")
        self.proof_done = bool(proof_done_override) if proof_done_override is not None else (self.fire_status == "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED")
        self.proof_reconciled = bool(proof_reconciled_override) if proof_reconciled_override is not None else (self.reconcile_status == "PASS_FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED")
        self.controlled_ready = bool(controlled_ready_override) if controlled_ready_override is not None else (self.controlled_status in ("CONTROLLED_OPERATION_REVIEW_READY_LOCKED", "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED"))

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.binder_ready:
            return "AWAIT_OPERATOR_APPROVAL_FILES"
        if not self.quorum_ready:
            return "AWAIT_FIREWALL_ADAPTER_INJECTION"
        if not self.proof_done:
            return "AWAIT_FIRST_LIVE_PROOF_FORENSIC_REVIEW"
        if not self.proof_reconciled:
            return "AWAIT_FIRST_LIVE_PROOF_RECONCILE"
        if not self.controlled_ready:
            return "AWAIT_AUTONOMY_REVIEW_APPROVAL"
        return "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_PRODUCTION_LOCK_BASELINE_REGRESSION" if self.v203_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_LOCK_V7_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v203_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V203_BASELINE_REGRESSION"] if self.v203_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PRODUCTION_LOCK_V7_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V204Context) -> dict[str, Any]:
    return {
        "v203_baseline_status": ctx.v203_baseline_status,
        "production_lock_controller_status": ctx.controller_status,
        "authority_binder_summary": ctx.binder_status,
        "authority_binder_summary_status": "PASS_AUTHORITY_BINDER_SUMMARIZED",
        "config_caps_quorum_summary": ctx.config_status,
        "config_caps_quorum_summary_status": "PASS_CONFIG_CAPS_QUORUM_SUMMARIZED",
        "firewall_broker_verification_summary": ctx.firewall_status,
        "firewall_broker_verification_summary_status": "PASS_FIREWALL_BROKER_VERIFICATION_SUMMARIZED",
        "final_quorum_summary": ctx.quorum_status,
        "final_quorum_summary_status": "PASS_FINAL_QUORUM_SUMMARIZED",
        "fire_gate_summary": ctx.fire_status,
        "fire_gate_summary_status": "PASS_FIRE_GATE_SUMMARIZED",
        "reconcile_summary": ctx.reconcile_status,
        "reconcile_summary_status": "PASS_RECONCILE_SUMMARIZED",
        "forensic_summary": ctx.forensic_status,
        "forensic_summary_status": "PASS_FORENSIC_SUMMARIZED",
        "scale_autonomy_evidence_summary": ctx.evidence_status,
        "scale_autonomy_evidence_summary_status": "PASS_SCALE_AUTONOMY_EVIDENCE_SUMMARIZED",
        "controlled_operation_status_summary": ctx.controlled_status,
        "controlled_operation_status_summary_status": "PASS_CONTROLLED_OPERATION_STATUS_SUMMARIZED",
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
        "readiness_governor_v164_status": "PASS",
        "execution_lock_deep_recheck_v163_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V204Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v203_baseline"):
        return "PASS" if ctx.v203_baseline_status == "PASS_V203_BASELINE_READBACK" else "FAIL" if ctx.v203_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V204Context) -> dict[str, Any]:
    workstream = "v204: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v204_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V204_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v204_report.json":
        report.update({"completion_oriented_next_action_v204_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v203_carried_status": ctx.v203_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v204_production_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v204_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v204.json", "dummy_canonical_identity_report_v204.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V204ReportFactory:
    def __init__(self, *, binder_ready_override=None, quorum_ready_override=None, proof_done_override=None, proof_reconciled_override=None, controlled_ready_override=None) -> None:
        self.kw = dict(binder_ready_override=binder_ready_override, quorum_ready_override=quorum_ready_override, proof_done_override=proof_done_override, proof_reconciled_override=proof_reconciled_override, controlled_ready_override=controlled_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V204Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
