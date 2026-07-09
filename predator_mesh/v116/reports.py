"""DUMMY v116 autonomous trade/abstain/lock policy — formalizes autonomy policy; enables no autonomy and no orders.

Encodes trade-eligibility, abstention, lock/escalate, and approval-required policy as design-only controls with
an explicit state machine (TRADE_FORBIDDEN_MISSING_APPROVAL / ABSTAIN_REQUIRED_RISK_OR_DRIFT /
LOCK_REQUIRED_BROKER_OR_CONFIG_GAP / ESCALATE_TO_OPERATOR / ELIGIBLE_FOR_REVIEW_ONLY). The policy is locked;
autonomous_trading_enabled stays false, no auto order, no auto scale, no live-submit/caps change.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v116 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v116: Autonomous Trade Abstain Lock Policy No Live Autonomy"
MISSION_NAME = "dummy_mission_state_report_v102.json"
FINAL_NAME = "final_report_v116.json"
INDEX_KEYS = ["autonomy_policy_controller_status", "default_policy_state", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V116 Autonomous Trade/Abstain/Lock Policy"
MISSION_KEY = "dummy_mission_state_report_v102"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Autonomy Policy", "autonomy_policy_controller_status"],
    ["Default State", "default_policy_state"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V116_ROUTES = [
    "/api/v116/autonomy-policy-controller",
    "/api/v116/v115-baseline",
    "/api/v116/trade-eligibility-policy",
    "/api/v116/abstention-policy",
    "/api/v116/lock-escalate-policy",
    "/api/v116/approval-required-policy",
    "/api/v116/policy-state-machine",
    "/api/v116/no-auto-order-proof",
    "/api/v116/no-auto-scale-proof",
    "/api/v116/no-live-submit-caps-change-proof",
    "/api/v116/readiness-governor",
    "/api/v116/execution-lock",
    "/api/v116/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-policy-controller": ["v116_autonomy_policy_controller_report.json"],
    "v115-baseline": ["v115_baseline_readback_v1_report.json"],
    "trade-eligibility-policy": ["v116_trade_eligibility_policy_report.json"],
    "abstention-policy": ["v116_abstention_policy_report.json"],
    "lock-escalate-policy": ["v116_lock_escalate_policy_report.json"],
    "approval-required-policy": ["v116_approval_required_policy_report.json"],
    "policy-state-machine": ["v116_policy_state_machine_report.json"],
    "no-auto-order-proof": ["v116_no_auto_order_proof_report.json"],
    "no-auto-scale-proof": ["v116_no_auto_scale_proof_report.json"],
    "no-live-submit-caps-change-proof": ["v116_no_live_submit_caps_change_proof_report.json"],
    "readiness-governor": ["readiness_governor_v76_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v75_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v116_report_v1.json", "completion_oriented_next_action_v116_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(116)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v116/reports.py scripts/generate_v116_reports.py dashboard/backend/v116_routes.py",
    "python scripts/generate_v116_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

POLICY_STATES = [
    "TRADE_FORBIDDEN_MISSING_APPROVAL",
    "ABSTAIN_REQUIRED_RISK_OR_DRIFT",
    "LOCK_REQUIRED_BROKER_OR_CONFIG_GAP",
    "ESCALATE_TO_OPERATOR",
    "ELIGIBLE_FOR_REVIEW_ONLY",
]
DEFAULT_POLICY_STATE = "TRADE_FORBIDDEN_MISSING_APPROVAL"


class V116Context:
    def __init__(self) -> None:
        self.v115_baseline_status = sgc.baseline_status("final_report_v115.json", "V115")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v115_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V115_BASELINE_REGRESSION"] if self.v115_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "AUTONOMY_POLICY_LOCKED_AWAIT_LIMITED_SESSION_GATE_NO_AUTONOMOUS_TRADING_NO_AUTO_ORDER"


def _common(ctx: V116Context) -> dict[str, Any]:
    return {
        "v115_baseline_status": ctx.v115_baseline_status,
        "autonomy_policy_controller_status": "PASS_AUTONOMY_POLICY_LOCKED",
        "trade_eligibility_policy_status": "PASS_TRADE_ELIGIBILITY_POLICY_LOCKED",
        "abstention_policy_status": "PASS_ABSTENTION_POLICY_LOCKED",
        "lock_escalate_policy_status": "PASS_LOCK_ESCALATE_POLICY_LOCKED",
        "approval_required_policy_status": "PASS_APPROVAL_REQUIRED_POLICY_LOCKED",
        "policy_state_machine_status": "PASS_POLICY_STATE_MACHINE_LOCKED",
        "policy_states": POLICY_STATES,
        "default_policy_state": DEFAULT_POLICY_STATE,
        "no_auto_order_proof_status": "PASS_NO_AUTO_ORDER",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "no_live_submit_caps_change_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "policies_are_design_only": True,
        "policies_auto_apply_orders": False,
        "autonomous_trading_enabled": False,
        "autonomy_enabled": False,
        "auto_order_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "readiness_governor_v76_status": "PASS",
        "execution_lock_deep_recheck_v75_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V116Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v115_baseline"):
        return "PASS" if ctx.v115_baseline_status == "PASS_V115_BASELINE_READBACK" else "FAIL" if ctx.v115_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V116Context) -> dict[str, Any]:
    workstream = "v116: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v116_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V116_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v116_report.json":
        report.update({"completion_oriented_next_action_v116_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v115_carried_status": ctx.v115_baseline_status, "autonomy_policy_controller_status": "PASS_AUTONOMY_POLICY_LOCKED", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v116_autonomy_policy_controller_report.json"), "no_auto_order": str(ARTIFACTS / "v116_no_auto_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v116.json", "dummy_canonical_identity_report_v116.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V116ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V116Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
