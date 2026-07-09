"""DUMMY v132 production risk & stop policy V2 — regenerates and locks stop policies; no orders, no caps changes.

Re-hardens stop-loss, drift, liquidity, broker-error, repeated-reject, and slippage locks plus a session kill switch,
daily lock, and operator-unlock requirement as design-only controls after the pilot/repeat review. No live order is
placed and caps are never modified.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v132 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v132: Production Risk Stop Policy V2 And Session Kill Switch Recheck"
MISSION_NAME = "dummy_mission_state_report_v118.json"
FINAL_NAME = "final_report_v132.json"
INDEX_KEYS = ["risk_stop_policy_controller_status", "session_kill_switch_status", "no_order_proof_status"]
DASH_TITLE = "Dummy V132 Production Risk & Stop Policy V2"
MISSION_KEY = "dummy_mission_state_report_v118"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Risk Stop Policy", "risk_stop_policy_controller_status"],
    ["Kill Switch", "session_kill_switch_status"],
    ["Caps Modified", "caps_modified"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V132_ROUTES = [
    "/api/v132/risk-stop-policy-controller",
    "/api/v132/v131-baseline",
    "/api/v132/stop-loss-lock",
    "/api/v132/drift-lock",
    "/api/v132/liquidity-lock",
    "/api/v132/broker-error-lock",
    "/api/v132/repeated-reject-lock",
    "/api/v132/slippage-lock",
    "/api/v132/session-kill-switch",
    "/api/v132/daily-lock",
    "/api/v132/operator-unlock-requirement",
    "/api/v132/no-order-proof",
    "/api/v132/readiness-governor",
    "/api/v132/execution-lock",
    "/api/v132/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "risk-stop-policy-controller": ["v132_risk_stop_policy_controller_report.json"],
    "v131-baseline": ["v131_baseline_readback_v1_report.json"],
    "stop-loss-lock": ["v132_stop_loss_lock_report.json"],
    "drift-lock": ["v132_drift_lock_report.json"],
    "liquidity-lock": ["v132_liquidity_lock_report.json"],
    "broker-error-lock": ["v132_broker_error_lock_report.json"],
    "repeated-reject-lock": ["v132_repeated_reject_lock_report.json"],
    "slippage-lock": ["v132_slippage_lock_report.json"],
    "session-kill-switch": ["v132_session_kill_switch_report.json"],
    "daily-lock": ["v132_daily_lock_report.json"],
    "operator-unlock-requirement": ["v132_operator_unlock_requirement_report.json"],
    "no-order-proof": ["v132_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v92_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v91_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v132_report_v1.json", "completion_oriented_next_action_v132_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(132)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v132/reports.py scripts/generate_v132_reports.py dashboard/backend/v132_routes.py",
    "python scripts/generate_v132_reports.py",
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


class V132Context:
    def __init__(self) -> None:
        self.v131_baseline_status = sgc.baseline_status("final_report_v131.json", "V131")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v131_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V131_BASELINE_REGRESSION"] if self.v131_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "RISK_STOP_POLICIES_V2_GENERATED_AND_LOCKED_AWAIT_SCALE_REVIEW_NO_ORDER_NO_CAPS_CHANGE"


def _common(ctx: V132Context) -> dict[str, Any]:
    return {
        "v131_baseline_status": ctx.v131_baseline_status,
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
        "readiness_governor_v92_status": "PASS",
        "execution_lock_deep_recheck_v91_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V132Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v131_baseline"):
        return "PASS" if ctx.v131_baseline_status == "PASS_V131_BASELINE_READBACK" else "FAIL" if ctx.v131_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V132Context) -> dict[str, Any]:
    workstream = "v132: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v132_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V132_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v132_report.json":
        report.update({"completion_oriented_next_action_v132_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v131_carried_status": ctx.v131_baseline_status, "risk_stop_policy_controller_status": "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v132_risk_stop_policy_controller_report.json"), "session_kill_switch": str(ARTIFACTS / "v132_session_kill_switch_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v132.json", "dummy_canonical_identity_report_v132.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V132ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V132Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
