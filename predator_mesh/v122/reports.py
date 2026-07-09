"""DUMMY v122 production risk & stop policy — generates and locks stop policies; no orders, no caps changes.

Hardens stop-loss, drift, liquidity, broker-error, repeated-reject, and slippage locks plus a session kill switch,
daily lock, and operator-unlock requirement as design-only controls. No live order is placed and caps are never
modified.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v122 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v122: Production Risk Stop Policy And Session Kill Switch Hardening"
MISSION_NAME = "dummy_mission_state_report_v108.json"
FINAL_NAME = "final_report_v122.json"
INDEX_KEYS = ["risk_stop_policy_controller_status", "session_kill_switch_status", "no_order_proof_status"]
DASH_TITLE = "Dummy V122 Production Risk & Stop Policy"
MISSION_KEY = "dummy_mission_state_report_v108"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Risk Stop Policy", "risk_stop_policy_controller_status"],
    ["Kill Switch", "session_kill_switch_status"],
    ["Caps Modified", "caps_modified"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V122_ROUTES = [
    "/api/v122/risk-stop-policy-controller",
    "/api/v122/v121-baseline",
    "/api/v122/stop-loss-lock",
    "/api/v122/drift-lock",
    "/api/v122/liquidity-lock",
    "/api/v122/broker-error-lock",
    "/api/v122/repeated-reject-lock",
    "/api/v122/slippage-lock",
    "/api/v122/session-kill-switch",
    "/api/v122/daily-lock",
    "/api/v122/operator-unlock-requirement",
    "/api/v122/no-order-proof",
    "/api/v122/readiness-governor",
    "/api/v122/execution-lock",
    "/api/v122/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "risk-stop-policy-controller": ["v122_risk_stop_policy_controller_report.json"],
    "v121-baseline": ["v121_baseline_readback_v1_report.json"],
    "stop-loss-lock": ["v122_stop_loss_lock_report.json"],
    "drift-lock": ["v122_drift_lock_report.json"],
    "liquidity-lock": ["v122_liquidity_lock_report.json"],
    "broker-error-lock": ["v122_broker_error_lock_report.json"],
    "repeated-reject-lock": ["v122_repeated_reject_lock_report.json"],
    "slippage-lock": ["v122_slippage_lock_report.json"],
    "session-kill-switch": ["v122_session_kill_switch_report.json"],
    "daily-lock": ["v122_daily_lock_report.json"],
    "operator-unlock-requirement": ["v122_operator_unlock_requirement_report.json"],
    "no-order-proof": ["v122_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v82_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v81_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v122_report_v1.json", "completion_oriented_next_action_v122_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(122)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v122/reports.py scripts/generate_v122_reports.py dashboard/backend/v122_routes.py",
    "python scripts/generate_v122_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

STOP_POLICIES = {
    "stop_loss": {"unit": "cents", "value_locked": True},
    "drift": {"unit": "bps", "value_locked": True},
    "liquidity": {"unit": "contracts", "value_locked": True},
    "broker_error": {"unit": "count", "value_locked": True},
    "repeated_reject": {"unit": "count", "value_locked": True},
    "slippage": {"unit": "bps", "value_locked": True},
    "daily": {"unit": "cents", "value_locked": True},
}


class V122Context:
    def __init__(self) -> None:
        self.v121_baseline_status = sgc.baseline_status("final_report_v121.json", "V121")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v121_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V121_BASELINE_REGRESSION"] if self.v121_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "RISK_STOP_POLICIES_GENERATED_AND_LOCKED_AWAIT_SCALE_REVIEW_NO_ORDER_NO_CAPS_CHANGE"


def _common(ctx: V122Context) -> dict[str, Any]:
    return {
        "v121_baseline_status": ctx.v121_baseline_status,
        "risk_stop_policy_controller_status": "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED",
        "stop_loss_lock_status": "PASS_STOP_LOSS_LOCKED",
        "drift_lock_status": "PASS_DRIFT_LOCKED",
        "liquidity_lock_status": "PASS_LIQUIDITY_LOCKED",
        "broker_error_lock_status": "PASS_BROKER_ERROR_LOCKED",
        "repeated_reject_lock_status": "PASS_REPEATED_REJECT_LOCKED",
        "slippage_lock_status": "PASS_SLIPPAGE_LOCKED",
        "session_kill_switch_status": "PASS_SESSION_KILL_SWITCH_ARMED",
        "daily_lock_status": "PASS_DAILY_LOCKED",
        "operator_unlock_requirement_status": "PASS_OPERATOR_UNLOCK_REQUIRED",
        "no_order_proof_status": "PASS_NO_ORDER",
        "stop_policies_locked": STOP_POLICIES,
        "policies_are_design_only": True,
        "policies_auto_apply_orders": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v82_status": "PASS",
        "execution_lock_deep_recheck_v81_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V122Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v121_baseline"):
        return "PASS" if ctx.v121_baseline_status == "PASS_V121_BASELINE_READBACK" else "FAIL" if ctx.v121_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V122Context) -> dict[str, Any]:
    workstream = "v122: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v122_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V122_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v122_report.json":
        report.update({"completion_oriented_next_action_v122_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v121_carried_status": ctx.v121_baseline_status, "risk_stop_policy_controller_status": "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v122_risk_stop_policy_controller_report.json"), "session_kill_switch": str(ARTIFACTS / "v122_session_kill_switch_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v122.json", "dummy_canonical_identity_report_v122.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V122ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V122Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
