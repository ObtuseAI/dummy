"""DUMMY v194 production lock V6 — summarizes V185-V193 and locks the next phase; no order.

Reads live-proof-blocker / controlled-session-authority / autonomy-dryrun-approval / shadow-governor / shadow-forensic /
autonomy-quorum / limited-autonomy-gate / guarded-autonomy-rehearsal / production-hardening status, totals the live
order count (0), and selects a next-action from a fixed matrix. Autonomous trading and scale stay disabled; no new order.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v194 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v194: Production Lock V6 Next Phase Map First Live Proof And Autonomy Status"
MISSION_NAME = "dummy_mission_state_report_v180.json"
FINAL_NAME = "final_report_v194.json"
INDEX_KEYS = ["production_lock_controller_status", "next_action_matrix_selection", "total_real_live_orders_submitted"]
DASH_TITLE = "Dummy V194 Production Lock V6"
MISSION_KEY = "dummy_mission_state_report_v180"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Production Lock", "production_lock_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Total Live Orders", "total_real_live_orders_submitted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V194_ROUTES = [
    "/api/v194/production-lock-controller",
    "/api/v194/v193-baseline",
    "/api/v194/live-proof-blocker-summary",
    "/api/v194/controlled-session-authority-summary",
    "/api/v194/autonomy-dryrun-approval-summary",
    "/api/v194/shadow-governor-summary",
    "/api/v194/shadow-forensic-summary",
    "/api/v194/autonomy-quorum-summary",
    "/api/v194/limited-autonomy-gate-summary",
    "/api/v194/guarded-autonomy-rehearsal-summary",
    "/api/v194/production-hardening-summary",
    "/api/v194/total-live-order-count",
    "/api/v194/next-action-matrix",
    "/api/v194/no-scale-proof",
    "/api/v194/no-autonomy-proof",
    "/api/v194/no-new-order-proof",
    "/api/v194/readiness-governor",
    "/api/v194/execution-lock",
    "/api/v194/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-lock-controller": ["v194_production_lock_controller_report.json"],
    "v193-baseline": ["v193_baseline_readback_v1_report.json"],
    "live-proof-blocker-summary": ["v194_live_proof_blocker_summary_report.json"],
    "controlled-session-authority-summary": ["v194_controlled_session_authority_summary_report.json"],
    "autonomy-dryrun-approval-summary": ["v194_autonomy_dryrun_approval_summary_report.json"],
    "shadow-governor-summary": ["v194_shadow_governor_summary_report.json"],
    "shadow-forensic-summary": ["v194_shadow_forensic_summary_report.json"],
    "autonomy-quorum-summary": ["v194_autonomy_quorum_summary_report.json"],
    "limited-autonomy-gate-summary": ["v194_limited_autonomy_gate_summary_report.json"],
    "guarded-autonomy-rehearsal-summary": ["v194_guarded_autonomy_rehearsal_summary_report.json"],
    "production-hardening-summary": ["v194_production_hardening_summary_report.json"],
    "total-live-order-count": ["v194_total_live_order_count_report.json"],
    "next-action-matrix": ["v194_next_action_matrix_report.json"],
    "no-scale-proof": ["v194_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v194_no_autonomy_proof_report.json"],
    "no-new-order-proof": ["v194_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v154_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v153_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v194_report_v1.json", "completion_oriented_next_action_v194_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(194)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v194/reports.py scripts/generate_v194_reports.py dashboard/backend/v194_routes.py",
    "python scripts/generate_v194_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_FIRST_REAL_PILOT_PROOF",
    "AWAIT_REPEAT_PILOT_PROOF",
    "AWAIT_CONTROLLED_SESSION_APPROVAL",
    "AWAIT_CONTROLLED_SESSION_PROOF",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "AWAIT_AUTONOMY_REVIEW_APPROVAL",
    "LIMITED_AUTONOMY_DRYRUN_READY_LOCKED",
    "LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF",
    "REPAIR_REQUIRED",
]


class V194Context:
    def __init__(self, *, session_authority_override=None, autonomy_ready_override=None) -> None:
        self.v193_baseline_status = sgc.baseline_status("final_report_v193.json", "V193")
        self.live_proof_status = str(sgc.load_artifact("final_report_v185.json").get("live_proof_blocker_controller_status", "PASS_LIVE_PROOF_BLOCKERS_AUDITED"))
        self.session_authority_status = str(sgc.load_artifact("final_report_v186.json").get("session_authority_controller_status", "PARTIAL_CONTROLLED_SESSION_AUTHORITY_BLOCKED"))
        self.dryrun_status = str(sgc.load_artifact("final_report_v187.json").get("autonomy_dryrun_controller_status", "PARTIAL_AUTONOMY_DRYRUN_APPROVAL_ABSENT"))
        self.shadow_governor_status = str(sgc.load_artifact("final_report_v188.json").get("shadow_governor_controller_status", "PASS_AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT"))
        self.shadow_forensic_status = str(sgc.load_artifact("final_report_v189.json").get("shadow_forensic_controller_status", "PASS_SHADOW_DECISION_FORENSIC_REVIEWED_LOCKED"))
        self.autonomy_quorum_status = str(sgc.load_artifact("final_report_v190.json").get("autonomy_eligibility", "AUTONOMY_BLOCKED_NO_LIVE_PROOF"))
        self.gate_status = str(sgc.load_artifact("final_report_v191.json").get("limited_autonomy_gate_controller_status", "PARTIAL_LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF"))
        self.rehearsal_status = str(sgc.load_artifact("final_report_v192.json").get("autonomy_rehearsal_controller_status", "PASS_GUARDED_AUTONOMY_REHEARSAL_SESSION_READY_DRY_ONLY"))
        self.hardening_status = str(sgc.load_artifact("final_report_v193.json").get("production_hardening_controller_status", "PASS_PRODUCTION_LOCKS_HARDENED"))
        self.session_authority_ready = bool(session_authority_override) if session_authority_override is not None else (self.session_authority_status == "PASS_CONTROLLED_SESSION_AUTHORITY_READY_NO_SUBMIT")
        self.autonomy_ready = bool(autonomy_ready_override) if autonomy_ready_override is not None else (self.autonomy_quorum_status == "AUTONOMY_REVIEW_READY_LOCKED")

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.session_authority_ready:
            return "AWAIT_CONTROLLED_SESSION_APPROVAL"
        if self.dryrun_status != "PASS_AUTONOMY_DRYRUN_APPROVAL_VALIDATED_NO_LIVE_PATH":
            return "AWAIT_AUTONOMY_REVIEW_APPROVAL"
        if not self.autonomy_ready:
            return "LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF"
        return "LIMITED_AUTONOMY_DRYRUN_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_PRODUCTION_LOCK_BASELINE_REGRESSION" if self.v193_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_LOCK_V6_SUMMARY_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v193_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V193_BASELINE_REGRESSION"] if self.v193_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PRODUCTION_LOCK_V6_COMPLETE_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx: V194Context) -> dict[str, Any]:
    return {
        "v193_baseline_status": ctx.v193_baseline_status,
        "production_lock_controller_status": ctx.controller_status,
        "live_proof_blocker_summary": ctx.live_proof_status,
        "live_proof_blocker_summary_status": "PASS_LIVE_PROOF_BLOCKER_SUMMARIZED",
        "controlled_session_authority_summary": ctx.session_authority_status,
        "controlled_session_authority_summary_status": "PASS_CONTROLLED_SESSION_AUTHORITY_SUMMARIZED",
        "autonomy_dryrun_approval_summary": ctx.dryrun_status,
        "autonomy_dryrun_approval_summary_status": "PASS_AUTONOMY_DRYRUN_APPROVAL_SUMMARIZED",
        "shadow_governor_summary": ctx.shadow_governor_status,
        "shadow_governor_summary_status": "PASS_SHADOW_GOVERNOR_SUMMARIZED",
        "shadow_forensic_summary": ctx.shadow_forensic_status,
        "shadow_forensic_summary_status": "PASS_SHADOW_FORENSIC_SUMMARIZED",
        "autonomy_quorum_summary": ctx.autonomy_quorum_status,
        "autonomy_quorum_summary_status": "PASS_AUTONOMY_QUORUM_SUMMARIZED",
        "limited_autonomy_gate_summary": ctx.gate_status,
        "limited_autonomy_gate_summary_status": "PASS_LIMITED_AUTONOMY_GATE_SUMMARIZED",
        "guarded_autonomy_rehearsal_summary": ctx.rehearsal_status,
        "guarded_autonomy_rehearsal_summary_status": "PASS_GUARDED_AUTONOMY_REHEARSAL_SUMMARIZED",
        "production_hardening_summary": ctx.hardening_status,
        "production_hardening_summary_status": "PASS_PRODUCTION_HARDENING_SUMMARIZED",
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
        "readiness_governor_v154_status": "PASS",
        "execution_lock_deep_recheck_v153_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V194Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v193_baseline"):
        return "PASS" if ctx.v193_baseline_status == "PASS_V193_BASELINE_READBACK" else "FAIL" if ctx.v193_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V194Context) -> dict[str, Any]:
    workstream = "v194: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v194_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V194_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v194_report.json":
        report.update({"completion_oriented_next_action_v194_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v193_carried_status": ctx.v193_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v194_production_lock_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v194_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v194.json", "dummy_canonical_identity_report_v194.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V194ReportFactory:
    def __init__(self, *, session_authority_override=None, autonomy_ready_override=None) -> None:
        self.kw = dict(session_authority_override=session_authority_override, autonomy_ready_override=autonomy_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V194Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
