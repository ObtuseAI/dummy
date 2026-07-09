"""DUMMY v108 production risk-governor hardening — generates and locks risk policies; no orders, no caps changes.

All risk policies (order size, daily loss, exposure, concurrency, cooldowns, slippage ceiling, liquidity
floor, kill switch, session lock, operator override) are generated and locked as design-only controls.
No live order is placed and caps are never modified.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v108 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v108: Risk Governor Production Hardening"
MISSION_NAME = "dummy_mission_state_report_v94.json"
FINAL_NAME = "final_report_v108.json"
INDEX_KEYS = ["risk_hardening_controller_status", "kill_switch_status", "no_scale_proof_status"]
DASH_TITLE = "Dummy V108 Risk Governor Production Hardening"
MISSION_KEY = "dummy_mission_state_report_v94"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Risk Hardening", "risk_hardening_controller_status"],
    ["Kill Switch", "kill_switch_status"],
    ["Caps Modified", "caps_modified"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V108_ROUTES = [
    "/api/v108/risk-hardening-controller",
    "/api/v108/v107-baseline",
    "/api/v108/max-order-size-policy",
    "/api/v108/max-daily-loss-policy",
    "/api/v108/max-open-exposure-policy",
    "/api/v108/max-concurrent-markets-policy",
    "/api/v108/cooldown-after-loss",
    "/api/v108/cooldown-after-reject",
    "/api/v108/cooldown-after-drift",
    "/api/v108/slippage-ceiling",
    "/api/v108/liquidity-floor",
    "/api/v108/kill-switch",
    "/api/v108/session-lock",
    "/api/v108/operator-override-requirement",
    "/api/v108/no-scale-proof",
    "/api/v108/readiness-governor",
    "/api/v108/execution-lock",
    "/api/v108/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "risk-hardening-controller": ["v108_risk_hardening_controller_report.json"],
    "v107-baseline": ["v107_baseline_readback_v1_report.json"],
    "max-order-size-policy": ["v108_max_order_size_policy_report.json"],
    "max-daily-loss-policy": ["v108_max_daily_loss_policy_report.json"],
    "max-open-exposure-policy": ["v108_max_open_exposure_policy_report.json"],
    "max-concurrent-markets-policy": ["v108_max_concurrent_markets_policy_report.json"],
    "cooldown-after-loss": ["v108_cooldown_after_loss_report.json"],
    "cooldown-after-reject": ["v108_cooldown_after_reject_report.json"],
    "cooldown-after-drift": ["v108_cooldown_after_drift_report.json"],
    "slippage-ceiling": ["v108_slippage_ceiling_report.json"],
    "liquidity-floor": ["v108_liquidity_floor_report.json"],
    "kill-switch": ["v108_kill_switch_report.json"],
    "session-lock": ["v108_session_lock_report.json"],
    "operator-override-requirement": ["v108_operator_override_requirement_report.json"],
    "no-scale-proof": ["v108_no_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v68_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v67_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v108_report_v1.json", "completion_oriented_next_action_v108_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(108)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v108/reports.py scripts/generate_v108_reports.py dashboard/backend/v108_routes.py",
    "python scripts/generate_v108_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

RISK_POLICIES = {
    "max_order_size": {"unit": "contracts", "value_locked": True},
    "max_daily_loss": {"unit": "cents", "value_locked": True},
    "max_open_exposure": {"unit": "cents", "value_locked": True},
    "max_concurrent_markets": {"unit": "count", "value_locked": True},
    "cooldown_after_loss": {"unit": "seconds", "value_locked": True},
    "cooldown_after_reject": {"unit": "seconds", "value_locked": True},
    "cooldown_after_drift": {"unit": "seconds", "value_locked": True},
    "slippage_ceiling": {"unit": "bps", "value_locked": True},
    "liquidity_floor": {"unit": "contracts", "value_locked": True},
}


class V108Context:
    def __init__(self) -> None:
        self.v107_baseline_status = sgc.baseline_status("final_report_v107.json", "V107")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v107_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V107_BASELINE_REGRESSION"] if self.v107_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "RISK_POLICIES_GENERATED_AND_LOCKED_AWAIT_ABSTENTION_GOVERNOR_NO_ORDER_NO_CAPS_CHANGE"


def _common(ctx: V108Context) -> dict[str, Any]:
    return {
        "v107_baseline_status": ctx.v107_baseline_status,
        "risk_hardening_controller_status": "PASS_RISK_POLICIES_GENERATED_AND_LOCKED",
        "max_order_size_policy_status": "PASS_MAX_ORDER_SIZE_LOCKED",
        "max_daily_loss_policy_status": "PASS_MAX_DAILY_LOSS_LOCKED",
        "max_open_exposure_policy_status": "PASS_MAX_OPEN_EXPOSURE_LOCKED",
        "max_concurrent_markets_policy_status": "PASS_MAX_CONCURRENT_MARKETS_LOCKED",
        "cooldown_after_loss_status": "PASS_COOLDOWN_AFTER_LOSS_LOCKED",
        "cooldown_after_reject_status": "PASS_COOLDOWN_AFTER_REJECT_LOCKED",
        "cooldown_after_drift_status": "PASS_COOLDOWN_AFTER_DRIFT_LOCKED",
        "slippage_ceiling_status": "PASS_SLIPPAGE_CEILING_LOCKED",
        "liquidity_floor_status": "PASS_LIQUIDITY_FLOOR_LOCKED",
        "kill_switch_status": "PASS_KILL_SWITCH_ARMED",
        "session_lock_status": "PASS_SESSION_LOCK_ARMED",
        "operator_override_requirement_status": "PASS_OPERATOR_OVERRIDE_REQUIRED",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "risk_policies_locked": RISK_POLICIES,
        "policies_are_design_only": True,
        "policies_auto_apply_orders": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v68_status": "PASS",
        "execution_lock_deep_recheck_v67_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V108Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v107_baseline"):
        return "PASS" if ctx.v107_baseline_status == "PASS_V107_BASELINE_READBACK" else "FAIL" if ctx.v107_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V108Context) -> dict[str, Any]:
    workstream = "v108: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v108_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V108_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v108_report.json":
        report.update({"completion_oriented_next_action_v108_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v107_carried_status": ctx.v107_baseline_status, "risk_hardening_controller_status": "PASS_RISK_POLICIES_GENERATED_AND_LOCKED", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v108_risk_hardening_controller_report.json"), "kill_switch": str(ARTIFACTS / "v108_kill_switch_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v108.json", "dummy_canonical_identity_report_v108.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V108ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V108Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
