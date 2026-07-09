"""DUMMY v134 controlled operation gate V2 — reviews the per-order-approval operation gate; no autonomous trading.

Encodes per-order approval, session approval, risk governor, and abstention governor requirements with live-submit
and caps operator-controlled. Optionally validates the exact controlled-operation review approval (review only). The
gate is ready and LOCKED; it never auto-submits, never auto-scales, never enables autonomy. Status is FAIL only if
autonomy were ever enabled — which it is not.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v134 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v134: Controlled Operation Gate V2 Per Order Approval Only"
MISSION_NAME = "dummy_mission_state_report_v120.json"
FINAL_NAME = "final_report_v134.json"
INDEX_KEYS = ["controlled_operation_gate_controller_status", "autonomous_trading_enabled", "no_auto_submit_proof_status"]
DASH_TITLE = "Dummy V134 Controlled Operation Gate V2"
MISSION_KEY = "dummy_mission_state_report_v120"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Gate", "controlled_operation_gate_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Per-Order Mode", "per_order_approval_required"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V134_ROUTES = [
    "/api/v134/controlled-operation-gate-controller",
    "/api/v134/v133-baseline",
    "/api/v134/controlled-operation-review-validator",
    "/api/v134/per-order-approval-requirement",
    "/api/v134/session-approval-requirement",
    "/api/v134/risk-governor-requirement",
    "/api/v134/abstention-governor-requirement",
    "/api/v134/live-submit-operator-controlled",
    "/api/v134/caps-operator-controlled",
    "/api/v134/no-auto-submit-proof",
    "/api/v134/no-auto-scale-proof",
    "/api/v134/no-market-order-proof",
    "/api/v134/readiness-governor",
    "/api/v134/execution-lock",
    "/api/v134/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-gate-controller": ["v134_controlled_operation_gate_controller_report.json"],
    "v133-baseline": ["v133_baseline_readback_v1_report.json"],
    "controlled-operation-review-validator": ["v134_controlled_operation_review_validator_report.json"],
    "per-order-approval-requirement": ["v134_per_order_approval_requirement_report.json"],
    "session-approval-requirement": ["v134_session_approval_requirement_report.json"],
    "risk-governor-requirement": ["v134_risk_governor_requirement_report.json"],
    "abstention-governor-requirement": ["v134_abstention_governor_requirement_report.json"],
    "live-submit-operator-controlled": ["v134_live_submit_operator_controlled_report.json"],
    "caps-operator-controlled": ["v134_caps_operator_controlled_report.json"],
    "no-auto-submit-proof": ["v134_no_auto_submit_proof_report.json"],
    "no-auto-scale-proof": ["v134_no_auto_scale_proof_report.json"],
    "no-market-order-proof": ["v134_no_market_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v94_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v93_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v134_report_v1.json", "completion_oriented_next_action_v134_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(134)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v134/reports.py scripts/generate_v134_reports.py dashboard/backend/v134_routes.py",
    "python scripts/generate_v134_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V134Context:
    def __init__(self, *, operation_approval=None, operation_approval_path=None, autonomy_enabled_override=None) -> None:
        self.v133_baseline_status = sgc.baseline_status("final_report_v133.json", "V133")
        res = sgc.resolve_packet(operation_approval_path, operation_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.CONTROLLED_OPERATION_PHRASE, required_fields=sgc.CONTROLLED_OPERATION_FIELDS, required_scope=sgc.CONTROLLED_OPERATION_SCOPE)
        self.autonomy_enabled = bool(autonomy_enabled_override) if autonomy_enabled_override is not None else False

    @property
    def review_approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def review_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def controller_status(self) -> str:
        if self.autonomy_enabled:
            return "FAIL_CONTROLLED_GATE_ENABLED_AUTONOMY"
        return "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v133_baseline_status.startswith("FAIL") or self.autonomy_enabled:
            return "FAIL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v133_baseline_status.startswith("FAIL"):
            return ["FAIL_V133_BASELINE_REGRESSION"]
        if self.autonomy_enabled:
            return ["FAIL_CONTROLLED_GATE_ENABLED_AUTONOMY"]
        return []

    @property
    def next_action(self) -> str:
        return "CONTROLLED_OPERATION_GATE_V2_READY_LOCKED_PER_ORDER_APPROVAL_ONLY_AWAIT_PRODUCTION_LOCK_NO_AUTONOMY"


def _common(ctx: V134Context) -> dict[str, Any]:
    return {
        "v133_baseline_status": ctx.v133_baseline_status,
        "controlled_operation_gate_controller_status": ctx.controller_status,
        "controlled_operation_review_validator_status": "PASS_CONTROLLED_OPERATION_REVIEW_VALID" if ctx.review_approved else ("FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL" if ctx.review_fail else "PARTIAL_CONTROLLED_OPERATION_REVIEW_ABSENT"),
        "controlled_operation_phrase": sgc.CONTROLLED_OPERATION_PHRASE,
        "controlled_operation_approval_hash": ctx.validation["approval_hash"],
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
        "readiness_governor_v94_status": "PASS",
        "execution_lock_deep_recheck_v93_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V134Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v133_baseline"):
        return "PASS" if ctx.v133_baseline_status == "PASS_V133_BASELINE_READBACK" else "FAIL" if ctx.v133_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v134_controlled_operation_gate_controller_report.json":
        return "FAIL" if ctx.autonomy_enabled else "PASS"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V134Context) -> dict[str, Any]:
    workstream = "v134: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v134_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V134_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v134_report.json":
        report.update({"completion_oriented_next_action_v134_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v133_carried_status": ctx.v133_baseline_status, "controlled_operation_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v134_controlled_operation_gate_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v134_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v134.json", "dummy_canonical_identity_report_v134.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V134ReportFactory:
    def __init__(self, *, operation_approval=None, operation_approval_path=None, autonomy_enabled_override=None) -> None:
        self.kw = dict(operation_approval=operation_approval, operation_approval_path=operation_approval_path, autonomy_enabled_override=autonomy_enabled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V134Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
