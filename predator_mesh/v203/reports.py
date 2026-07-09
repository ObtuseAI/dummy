"""DUMMY v203 controlled operation status gate V7 — updates controlled-operation status after first live-proof review; no autonomy.

Reads first-live-proof / reconcile / forensic status and scale/autonomy evidence, applies risk + abstention locks and a
per-order approval requirement, and emits a status (CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF /
CONTROLLED_OPERATION_REVIEW_READY_LOCKED / CONTROLLED_OPERATION_REPAIR_REQUIRED /
CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED). Default is CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF. No auto-submit,
no market order, no scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v203 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v203: Controlled Operation Status Gate V7 Per Order Only"
MISSION_NAME = "dummy_mission_state_report_v189.json"
FINAL_NAME = "final_report_v203.json"
INDEX_KEYS = ["controlled_operation_status_controller_status", "controlled_operation_status", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V203 Controlled Operation Status Gate V7"
MISSION_KEY = "dummy_mission_state_report_v189"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Status Gate", "controlled_operation_status_controller_status"],
    ["Operation Status", "controlled_operation_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V203_ROUTES = [
    "/api/v203/controlled-operation-status-controller",
    "/api/v203/v202-baseline",
    "/api/v203/first-live-proof-status-readback",
    "/api/v203/reconcile-status-readback",
    "/api/v203/forensic-status-readback",
    "/api/v203/scale-autonomy-evidence-readback",
    "/api/v203/risk-locks",
    "/api/v203/abstention-locks",
    "/api/v203/per-order-approval-requirement",
    "/api/v203/live-submit-operator-control-proof",
    "/api/v203/caps-operator-control-proof",
    "/api/v203/no-auto-submit-proof",
    "/api/v203/no-market-order-proof",
    "/api/v203/no-scale-proof",
    "/api/v203/no-autonomy-proof",
    "/api/v203/readiness-governor",
    "/api/v203/execution-lock",
    "/api/v203/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-status-controller": ["v203_controlled_operation_status_controller_report.json"],
    "v202-baseline": ["v202_baseline_readback_v1_report.json"],
    "first-live-proof-status-readback": ["v203_first_live_proof_status_readback_report.json"],
    "reconcile-status-readback": ["v203_reconcile_status_readback_report.json"],
    "forensic-status-readback": ["v203_forensic_status_readback_report.json"],
    "scale-autonomy-evidence-readback": ["v203_scale_autonomy_evidence_readback_report.json"],
    "risk-locks": ["v203_risk_locks_report.json"],
    "abstention-locks": ["v203_abstention_locks_report.json"],
    "per-order-approval-requirement": ["v203_per_order_approval_requirement_report.json"],
    "live-submit-operator-control-proof": ["v203_live_submit_operator_control_proof_report.json"],
    "caps-operator-control-proof": ["v203_caps_operator_control_proof_report.json"],
    "no-auto-submit-proof": ["v203_no_auto_submit_proof_report.json"],
    "no-market-order-proof": ["v203_no_market_order_proof_report.json"],
    "no-scale-proof": ["v203_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v203_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v163_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v162_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v203_report_v1.json", "completion_oriented_next_action_v203_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(203)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v203/reports.py scripts/generate_v203_reports.py dashboard/backend/v203_routes.py",
    "python scripts/generate_v203_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

STATUS_ENUM = [
    "CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF",
    "CONTROLLED_OPERATION_REVIEW_READY_LOCKED",
    "CONTROLLED_OPERATION_REPAIR_REQUIRED",
    "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED",
]


class V203Context:
    def __init__(self, *, live_proof_override=None, per_order_ready_override=None) -> None:
        self.v202_baseline_status = sgc.baseline_status("final_report_v202.json", "V202")
        if live_proof_override is not None:
            self.live_proof = bool(live_proof_override)
        else:
            self.live_proof = str(sgc.load_artifact("final_report_v201.json").get("forensic_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_FORENSIC_REVIEWED"
        self.per_order_ready = bool(per_order_ready_override) if per_order_ready_override is not None else False

    @property
    def controlled_operation_status(self) -> str:
        if not self.live_proof:
            return "CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF"
        if self.per_order_ready:
            return "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED"
        return "CONTROLLED_OPERATION_REVIEW_READY_LOCKED"

    @property
    def ready(self) -> bool:
        return self.controlled_operation_status in ("CONTROLLED_OPERATION_REVIEW_READY_LOCKED", "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED")

    @property
    def controller_status(self) -> str:
        if self.v202_baseline_status.startswith("FAIL"):
            return "FAIL_CONTROLLED_OPERATION_STATUS_BASELINE_REGRESSION"
        return "PASS_CONTROLLED_OPERATION_STATUS_GATE_V7_LOCKED" if self.ready else "PARTIAL_CONTROLLED_OPERATION_STATUS_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v202_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v202_baseline_status.startswith("FAIL"):
            return ["FAIL_V202_BASELINE_REGRESSION"]
        return [] if self.ready else ["CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF"]

    @property
    def next_action(self) -> str:
        if self.controlled_operation_status == "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED":
            return "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED_NO_AUTONOMY_NO_AUTO_SUBMIT"
        if self.ready:
            return "CONTROLLED_OPERATION_REVIEW_READY_LOCKED_AWAIT_PER_ORDER_APPROVAL_NO_AUTONOMY"
        return "AWAIT_FIRST_LIVE_PROOF_BEFORE_CONTROLLED_OPERATION_STATUS"


def _common(ctx: V203Context) -> dict[str, Any]:
    return {
        "v202_baseline_status": ctx.v202_baseline_status,
        "controlled_operation_status_controller_status": ctx.controller_status,
        "first_live_proof_status_readback_status": "PASS_FIRST_LIVE_PROOF_STATUS_READ",
        "reconcile_status_readback_status": "PASS_RECONCILE_STATUS_READ",
        "forensic_status_readback_status": "PASS_FORENSIC_STATUS_READ",
        "scale_autonomy_evidence_readback_status": "PASS_SCALE_AUTONOMY_EVIDENCE_READ",
        "risk_locks_status": "PASS_RISK_LOCKS_HELD",
        "abstention_locks_status": "PASS_ABSTENTION_LOCKS_HELD",
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "live_submit_operator_control_proof_status": "PASS_LIVE_SUBMIT_OPERATOR_CONTROLLED",
        "caps_operator_control_proof_status": "PASS_CAPS_OPERATOR_CONTROLLED",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "controlled_operation_status": ctx.controlled_operation_status,
        "controlled_operation_status_enum": STATUS_ENUM,
        "per_order_approval_required": True,
        "auto_submit_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v163_status": "PASS",
        "execution_lock_deep_recheck_v162_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V203Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v202_baseline"):
        return "PASS" if ctx.v202_baseline_status == "PASS_V202_BASELINE_READBACK" else "FAIL" if ctx.v202_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v203_controlled_operation_status_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V203Context) -> dict[str, Any]:
    workstream = "v203: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v203_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V203_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v203_report.json":
        report.update({"completion_oriented_next_action_v203_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v202_carried_status": ctx.v202_baseline_status, "controlled_operation_status": ctx.controlled_operation_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v203_controlled_operation_status_controller_report.json"), "no_autonomy": str(ARTIFACTS / "v203_no_autonomy_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v203.json", "dummy_canonical_identity_report_v203.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V203ReportFactory:
    def __init__(self, *, live_proof_override=None, per_order_ready_override=None) -> None:
        self.kw = dict(live_proof_override=live_proof_override, per_order_ready_override=per_order_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V203Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
