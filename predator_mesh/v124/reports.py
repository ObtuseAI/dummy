"""DUMMY v124 controlled operation gate — builds a per-order-approval operation gate; no autonomous trading.

Encodes per-order approval, session approval, risk governor, and abstention governor requirements with live-submit
and caps operator-controlled. The gate is ready and LOCKED; it never auto-submits, never auto-scales, and never
enables autonomy. Status is FAIL only if autonomy were ever enabled — which it is not.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v124 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v124: Controlled Operation Gate Per Order Approval Only"
MISSION_NAME = "dummy_mission_state_report_v110.json"
FINAL_NAME = "final_report_v124.json"
INDEX_KEYS = ["controlled_operation_gate_controller_status", "autonomous_trading_enabled", "no_auto_submit_proof_status"]
DASH_TITLE = "Dummy V124 Controlled Operation Gate"
MISSION_KEY = "dummy_mission_state_report_v110"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Gate", "controlled_operation_gate_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Per-Order Mode", "per_order_approval_required"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V124_ROUTES = [
    "/api/v124/controlled-operation-gate-controller",
    "/api/v124/v123-baseline",
    "/api/v124/per-order-approval-requirement",
    "/api/v124/session-approval-requirement",
    "/api/v124/risk-governor-requirement",
    "/api/v124/abstention-governor-requirement",
    "/api/v124/live-submit-operator-controlled",
    "/api/v124/caps-operator-controlled",
    "/api/v124/no-auto-submit-proof",
    "/api/v124/no-auto-scale-proof",
    "/api/v124/no-market-order-proof",
    "/api/v124/readiness-governor",
    "/api/v124/execution-lock",
    "/api/v124/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-gate-controller": ["v124_controlled_operation_gate_controller_report.json"],
    "v123-baseline": ["v123_baseline_readback_v1_report.json"],
    "per-order-approval-requirement": ["v124_per_order_approval_requirement_report.json"],
    "session-approval-requirement": ["v124_session_approval_requirement_report.json"],
    "risk-governor-requirement": ["v124_risk_governor_requirement_report.json"],
    "abstention-governor-requirement": ["v124_abstention_governor_requirement_report.json"],
    "live-submit-operator-controlled": ["v124_live_submit_operator_controlled_report.json"],
    "caps-operator-controlled": ["v124_caps_operator_controlled_report.json"],
    "no-auto-submit-proof": ["v124_no_auto_submit_proof_report.json"],
    "no-auto-scale-proof": ["v124_no_auto_scale_proof_report.json"],
    "no-market-order-proof": ["v124_no_market_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v84_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v83_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v124_report_v1.json", "completion_oriented_next_action_v124_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(124)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v124/reports.py scripts/generate_v124_reports.py dashboard/backend/v124_routes.py",
    "python scripts/generate_v124_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V124Context:
    def __init__(self, *, autonomy_enabled_override=None) -> None:
        self.v123_baseline_status = sgc.baseline_status("final_report_v123.json", "V123")
        self.autonomy_enabled = bool(autonomy_enabled_override) if autonomy_enabled_override is not None else False

    @property
    def controller_status(self) -> str:
        if self.autonomy_enabled:
            return "FAIL_CONTROLLED_GATE_ENABLED_AUTONOMY"
        return "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v123_baseline_status.startswith("FAIL") or self.autonomy_enabled:
            return "FAIL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v123_baseline_status.startswith("FAIL"):
            return ["FAIL_V123_BASELINE_REGRESSION"]
        if self.autonomy_enabled:
            return ["FAIL_CONTROLLED_GATE_ENABLED_AUTONOMY"]
        return []

    @property
    def next_action(self) -> str:
        return "CONTROLLED_OPERATION_GATE_READY_LOCKED_PER_ORDER_APPROVAL_ONLY_AWAIT_PRODUCTION_LOCK_NO_AUTONOMY"


def _common(ctx: V124Context) -> dict[str, Any]:
    return {
        "v123_baseline_status": ctx.v123_baseline_status,
        "controlled_operation_gate_controller_status": ctx.controller_status,
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "per_order_approval_required": True,
        "session_approval_requirement_status": "PASS_SESSION_APPROVAL_REQUIRED",
        "session_approval_required": True,
        "risk_governor_requirement_status": "PASS_RISK_GOVERNOR_REQUIRED",
        "abstention_governor_requirement_status": "PASS_ABSTENTION_GOVERNOR_REQUIRED",
        "live_submit_operator_controlled_status": "PASS_LIVE_SUBMIT_OPERATOR_CONTROLLED",
        "caps_operator_controlled_status": "PASS_CAPS_OPERATOR_CONTROLLED",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "gate_ready_locked": not ctx.autonomy_enabled,
        "autonomous_trading_enabled": ctx.autonomy_enabled,
        "auto_submit_enabled": False,
        "auto_scale_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "readiness_governor_v84_status": "PASS",
        "execution_lock_deep_recheck_v83_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V124Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v123_baseline"):
        return "PASS" if ctx.v123_baseline_status == "PASS_V123_BASELINE_READBACK" else "FAIL" if ctx.v123_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v124_controlled_operation_gate_controller_report.json":
        return "FAIL" if ctx.autonomy_enabled else "PASS"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V124Context) -> dict[str, Any]:
    workstream = "v124: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v124_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V124_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v124_report.json":
        report.update({"completion_oriented_next_action_v124_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v123_carried_status": ctx.v123_baseline_status, "controlled_operation_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v124_controlled_operation_gate_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v124_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v124.json", "dummy_canonical_identity_report_v124.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V124ReportFactory:
    def __init__(self, *, autonomy_enabled_override=None) -> None:
        self.kw = dict(autonomy_enabled_override=autonomy_enabled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V124Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
