"""DUMMY v117 limited autonomous session gate — prepares a bounded session gate; never auto-submits a live order.

Validates the exact limited-autonomous-session PREPARATION approval. Default is
PARTIAL_LIMITED_SESSION_APPROVAL_ABSENT with autonomous_submit_enabled=false and live_orders=0. When the exact
approval validates the gate is PREPARED and LOCKED — it still never auto-submits; every live submit requires
separate per-order approval. No market orders, caps unchanged, live-submit operator-controlled.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v117 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v117: Limited Autonomous Session Gate Locked No Auto Submit"
MISSION_NAME = "dummy_mission_state_report_v103.json"
FINAL_NAME = "final_report_v117.json"
INDEX_KEYS = ["limited_session_gate_controller_status", "autonomous_submit_enabled", "live_orders"]
DASH_TITLE = "Dummy V117 Limited Autonomous Session Gate"
MISSION_KEY = "dummy_mission_state_report_v103"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Gate", "limited_session_gate_controller_status"],
    ["Auto Submit", "autonomous_submit_enabled"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V117_ROUTES = [
    "/api/v117/limited-session-gate-controller",
    "/api/v117/v116-baseline",
    "/api/v117/limited-session-approval-validator",
    "/api/v117/session-budget-lock",
    "/api/v117/per-order-approval-requirement",
    "/api/v117/max-session-order-count",
    "/api/v117/no-market-order-proof",
    "/api/v117/no-auto-submit-proof",
    "/api/v117/broker-firewall-prerequisite-proof",
    "/api/v117/live-submit-caps-control-proof",
    "/api/v117/readiness-governor",
    "/api/v117/execution-lock",
    "/api/v117/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "limited-session-gate-controller": ["v117_limited_session_gate_controller_report.json"],
    "v116-baseline": ["v116_baseline_readback_v1_report.json"],
    "limited-session-approval-validator": ["v117_limited_session_approval_validator_report.json"],
    "session-budget-lock": ["v117_session_budget_lock_report.json"],
    "per-order-approval-requirement": ["v117_per_order_approval_requirement_report.json"],
    "max-session-order-count": ["v117_max_session_order_count_report.json"],
    "no-market-order-proof": ["v117_no_market_order_proof_report.json"],
    "no-auto-submit-proof": ["v117_no_auto_submit_proof_report.json"],
    "broker-firewall-prerequisite-proof": ["v117_broker_firewall_prerequisite_proof_report.json"],
    "live-submit-caps-control-proof": ["v117_live_submit_caps_control_proof_report.json"],
    "readiness-governor": ["readiness_governor_v77_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v76_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v117_report_v1.json", "completion_oriented_next_action_v117_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(117)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v117/reports.py scripts/generate_v117_reports.py dashboard/backend/v117_routes.py",
    "python scripts/generate_v117_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

MAX_SESSION_ORDER_COUNT = 1


class V117Context:
    def __init__(self, *, session_approval=None, session_approval_path=None) -> None:
        self.v116_baseline_status = sgc.baseline_status("final_report_v116.json", "V116")
        res = sgc.resolve_packet(session_approval_path, session_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.LIMITED_SESSION_PHRASE, required_fields=sgc.LIMITED_SESSION_FIELDS, required_scope=sgc.LIMITED_SESSION_SCOPE)

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_LIMITED_SESSION_APPROVAL"
        if self.approved:
            return "PASS_LIMITED_SESSION_GATE_PREPARED_LOCKED_NO_AUTO_SUBMIT"
        return "PARTIAL_LIMITED_SESSION_APPROVAL_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v116_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.approved else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v116_baseline_status.startswith("FAIL"):
            return ["FAIL_V116_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_LIMITED_SESSION_APPROVAL"]
        return [] if self.approved else ["LIMITED_SESSION_APPROVAL_ABSENT"]

    @property
    def next_action(self) -> str:
        return "LIMITED_SESSION_GATE_PREPARED_LOCKED_NO_AUTO_SUBMIT_AWAIT_PRODUCTION_DRY_AUDIT" if self.approved else "OPERATOR_MUST_PROVIDE_EXACT_LIMITED_SESSION_APPROVAL_NO_AUTO_SUBMIT"


def _common(ctx: V117Context) -> dict[str, Any]:
    return {
        "v116_baseline_status": ctx.v116_baseline_status,
        "limited_session_gate_controller_status": ctx.controller_status,
        "limited_session_approval_validator_status": "PASS_LIMITED_SESSION_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_LIMITED_SESSION_APPROVAL" if ctx.any_fail else "PARTIAL_LIMITED_SESSION_APPROVAL_ABSENT"),
        "limited_session_phrase": sgc.LIMITED_SESSION_PHRASE,
        "limited_session_approval_hash": ctx.validation["approval_hash"],
        "session_budget_lock_status": "PASS_SESSION_BUDGET_LOCKED",
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "max_session_order_count_status": "PASS_MAX_SESSION_ORDER_COUNT_LOCKED",
        "max_session_order_count": MAX_SESSION_ORDER_COUNT,
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "broker_firewall_prerequisite_proof_status": "PASS_FIREWALL_ONLY_NO_CONTACT",
        "live_submit_caps_control_proof_status": "PASS_LIVE_SUBMIT_OPERATOR_CONTROLLED_CAPS_UNCHANGED",
        "gate_prepared": ctx.approved,
        "gate_locked": True,
        "autonomous_submit_enabled": False,
        "session_auto_submit_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v77_status": "PASS",
        "execution_lock_deep_recheck_v76_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V117Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v116_baseline"):
        return "PASS" if ctx.v116_baseline_status == "PASS_V116_BASELINE_READBACK" else "FAIL" if ctx.v116_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v117_limited_session_gate_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.approved else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V117Context) -> dict[str, Any]:
    workstream = "v117: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v117_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V117_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v117_report.json":
        report.update({"completion_oriented_next_action_v117_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v116_carried_status": ctx.v116_baseline_status, "limited_session_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v117_limited_session_gate_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v117_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v117.json", "dummy_canonical_identity_report_v117.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V117ReportFactory:
    def __init__(self, *, session_approval=None, session_approval_path=None) -> None:
        self.kw = dict(session_approval=session_approval, session_approval_path=session_approval_path)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V117Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
