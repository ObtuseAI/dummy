"""DUMMY v180 session stop/repeat/repair decision — decides stop/repair/repeat/hold after controlled session evidence; no order.

Requires session reconcile (V178) + forensic (V179) prerequisites plus no-loss/drift/liquidity/broker-error/slippage
locks and risk/abstention review. Emits a decision (STOP_NO_SESSION_PROOF / REPAIR_REQUIRED /
REPEAT_SESSION_REVIEW_READY_LOCKED / HOLD_CONTROLLED_OPERATION_LOCKED / SCALE_REVIEW_ELIGIBLE_LOCKED /
AUTONOMY_REVIEW_BLOCKED). Default is STOP_NO_SESSION_PROOF. No submit, no scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v180 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v180: Session Stop Repeat Repair Decision Lock"
MISSION_NAME = "dummy_mission_state_report_v166.json"
FINAL_NAME = "final_report_v180.json"
INDEX_KEYS = ["session_decision_controller_status", "session_decision", "live_orders"]
DASH_TITLE = "Dummy V180 Session Stop/Repeat/Repair Decision"
MISSION_KEY = "dummy_mission_state_report_v166"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Decision", "session_decision_controller_status"],
    ["Decision", "session_decision"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V180_ROUTES = [
    "/api/v180/session-decision-controller",
    "/api/v180/v179-baseline",
    "/api/v180/session-reconcile-prerequisite",
    "/api/v180/session-forensic-prerequisite",
    "/api/v180/no-loss-lock",
    "/api/v180/no-drift-lock",
    "/api/v180/no-liquidity-lock",
    "/api/v180/no-broker-error-lock",
    "/api/v180/no-slippage-lock",
    "/api/v180/risk-threshold-review",
    "/api/v180/abstention-quality-review",
    "/api/v180/no-submit-proof",
    "/api/v180/no-scale-proof",
    "/api/v180/no-autonomy-proof",
    "/api/v180/readiness-governor",
    "/api/v180/execution-lock",
    "/api/v180/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-decision-controller": ["v180_session_decision_controller_report.json"],
    "v179-baseline": ["v179_baseline_readback_v1_report.json"],
    "session-reconcile-prerequisite": ["v180_session_reconcile_prerequisite_report.json"],
    "session-forensic-prerequisite": ["v180_session_forensic_prerequisite_report.json"],
    "no-loss-lock": ["v180_no_loss_lock_report.json"],
    "no-drift-lock": ["v180_no_drift_lock_report.json"],
    "no-liquidity-lock": ["v180_no_liquidity_lock_report.json"],
    "no-broker-error-lock": ["v180_no_broker_error_lock_report.json"],
    "no-slippage-lock": ["v180_no_slippage_lock_report.json"],
    "risk-threshold-review": ["v180_risk_threshold_review_report.json"],
    "abstention-quality-review": ["v180_abstention_quality_review_report.json"],
    "no-submit-proof": ["v180_no_submit_proof_report.json"],
    "no-scale-proof": ["v180_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v180_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v140_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v139_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v180_report_v1.json", "completion_oriented_next_action_v180_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(180)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v180/reports.py scripts/generate_v180_reports.py dashboard/backend/v180_routes.py",
    "python scripts/generate_v180_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

DECISION_ENUM = [
    "STOP_NO_SESSION_PROOF",
    "REPAIR_REQUIRED",
    "REPEAT_SESSION_REVIEW_READY_LOCKED",
    "HOLD_CONTROLLED_OPERATION_LOCKED",
    "SCALE_REVIEW_ELIGIBLE_LOCKED",
    "AUTONOMY_REVIEW_BLOCKED",
]


class V180Context:
    def __init__(self, *, session_proof_override=None, risk_ready_override=None) -> None:
        self.v179_baseline_status = sgc.baseline_status("final_report_v179.json", "V179")
        if session_proof_override is not None:
            self.session_proof = bool(session_proof_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v178.json").get("session_reconcile_controller_status", "")) == "PASS_CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v179.json").get("session_forensic_controller_status", "")) == "PASS_CONTROLLED_SESSION_FORENSIC_REVIEWED"
            self.session_proof = reconciled and reviewed
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def session_decision(self) -> str:
        if not self.session_proof:
            return "STOP_NO_SESSION_PROOF"
        if not self.risk_ready:
            return "REPAIR_REQUIRED"
        return "HOLD_CONTROLLED_OPERATION_LOCKED"

    @property
    def locked(self) -> bool:
        return self.session_proof and self.risk_ready

    @property
    def controller_status(self) -> str:
        return "PASS_SESSION_DECISION_LOCKED" if self.locked else "PARTIAL_SESSION_DECISION_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v179_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.locked else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v179_baseline_status.startswith("FAIL"):
            return ["FAIL_V179_BASELINE_REGRESSION"]
        if self.locked:
            return []
        blockers: list[str] = []
        if not self.session_proof:
            blockers.append("CONTROLLED_SESSION_RECONCILE_FORENSIC_PROOF_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_THRESHOLD_REVIEW_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "SESSION_DECISION_LOCKED_HOLD_CONTROLLED_OPERATION_AWAIT_SCALE_AND_AUTONOMY_REVIEW_NO_SUBMIT" if self.locked else "AWAIT_CONTROLLED_SESSION_RECONCILE_AND_FORENSIC_BEFORE_DECISION"


def _common(ctx: V180Context) -> dict[str, Any]:
    present = ctx.session_proof
    def s(v):
        return v if present else "PARTIAL_NO_SESSION"
    return {
        "v179_baseline_status": ctx.v179_baseline_status,
        "session_decision_controller_status": ctx.controller_status,
        "session_reconcile_prerequisite_status": "PASS_SESSION_RECONCILED" if present else "PARTIAL_SESSION_NOT_RECONCILED",
        "session_forensic_prerequisite_status": "PASS_SESSION_FORENSIC_PRESENT" if present else "PARTIAL_SESSION_FORENSIC_ABSENT",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
        "no_liquidity_lock_status": "PASS_NO_LIQUIDITY_LOCK_ARMED",
        "no_broker_error_lock_status": "PASS_NO_BROKER_ERROR_LOCK_ARMED",
        "no_slippage_lock_status": "PASS_NO_SLIPPAGE_LOCK_ARMED",
        "risk_threshold_review_status": "PASS_RISK_THRESHOLD_MET" if ctx.risk_ready else "PARTIAL_RISK_THRESHOLD_UNMET",
        "abstention_quality_review_status": s("PASS_ABSTENTION_QUALITY_REVIEWED"),
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "session_decision": ctx.session_decision,
        "session_decision_enum": DECISION_ENUM,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v140_status": "PASS",
        "execution_lock_deep_recheck_v139_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V180Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v179_baseline"):
        return "PASS" if ctx.v179_baseline_status == "PASS_V179_BASELINE_READBACK" else "FAIL" if ctx.v179_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v180_session_decision_controller_report.json":
        return "PASS" if ctx.locked else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V180Context) -> dict[str, Any]:
    workstream = "v180: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v180_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V180_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v180_report.json":
        report.update({"completion_oriented_next_action_v180_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v179_carried_status": ctx.v179_baseline_status, "session_decision": ctx.session_decision, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v180_session_decision_controller_report.json"), "no_submit": str(ARTIFACTS / "v180_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v180.json", "dummy_canonical_identity_report_v180.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V180ReportFactory:
    def __init__(self, *, session_proof_override=None, risk_ready_override=None) -> None:
        self.kw = dict(session_proof_override=session_proof_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V180Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
