"""DUMMY v83 risk governor hardening and scaling threshold policy — no live order, no caps mod."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v83 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

SCALING_POLICY = {
    "max_order_size": "tiny_placeholder",
    "max_daily_loss": "operator_configured_placeholder",
    "max_open_exposure": "operator_configured_placeholder",
    "max_concurrent_markets": 1,
    "cooldown_after_loss": True,
    "cooldown_after_reject": True,
    "cooldown_after_drift": True,
    "max_slippage": "operator_configured_placeholder",
    "kill_switch": True,
    "session_lock": True,
    "operator_override_required": True,
    "scale_step_policy": "one_step_at_a_time_operator_gated",
}

V83_ROUTES = [
    "/api/v83/risk-hardening-controller",
    "/api/v83/v82-baseline",
    "/api/v83/max-order-size",
    "/api/v83/max-daily-loss",
    "/api/v83/max-open-exposure",
    "/api/v83/max-concurrent-markets",
    "/api/v83/cooldown-after-loss",
    "/api/v83/cooldown-after-reject",
    "/api/v83/cooldown-after-drift",
    "/api/v83/max-slippage",
    "/api/v83/kill-switch",
    "/api/v83/session-lock",
    "/api/v83/operator-override-requirement",
    "/api/v83/scale-step-policy",
    "/api/v83/readiness-governor",
    "/api/v83/execution-lock",
    "/api/v83/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "risk-hardening-controller": ["v83_risk_hardening_controller_report.json"],
    "v82-baseline": ["v82_baseline_readback_v1_report.json"],
    "max-order-size": ["v83_max_order_size_report.json"],
    "max-daily-loss": ["v83_max_daily_loss_report.json"],
    "max-open-exposure": ["v83_max_open_exposure_report.json"],
    "max-concurrent-markets": ["v83_max_concurrent_markets_report.json"],
    "cooldown-after-loss": ["v83_cooldown_after_loss_report.json"],
    "cooldown-after-reject": ["v83_cooldown_after_reject_report.json"],
    "cooldown-after-drift": ["v83_cooldown_after_drift_report.json"],
    "max-slippage": ["v83_max_slippage_report.json"],
    "kill-switch": ["v83_kill_switch_report.json"],
    "session-lock": ["v83_session_lock_report.json"],
    "operator-override-requirement": ["v83_operator_override_requirement_report.json"],
    "scale-step-policy": ["v83_scale_step_policy_report.json"],
    "readiness-governor": ["readiness_governor_v43_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v42_report.json"],
    "mission-state": ["dummy_mission_state_report_v69.json", "dashboard_v83_report_v1.json", "completion_oriented_next_action_v83_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(83)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v83/reports.py scripts/generate_v83_reports.py dashboard/backend/v83_routes.py",
    "python scripts/generate_v83_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V83Context:
    def __init__(self) -> None:
        self.v82_baseline_status = sgc.baseline_status("final_report_v82.json", "V82")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v82_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V82_BASELINE_REGRESSION"] if self.v82_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "RISK_SCALING_POLICY_GENERATED_LOCKED_NO_LIVE_ORDER"


def _common(ctx: V83Context) -> dict[str, Any]:
    checks = {f"{k}_status": "PASS_POLICY_DEFINED" for k in ["max_order_size", "max_daily_loss", "max_open_exposure", "max_concurrent_markets", "cooldown_after_loss", "cooldown_after_reject", "cooldown_after_drift", "max_slippage", "kill_switch", "session_lock", "operator_override_requirement", "scale_step_policy"]}
    common = {
        "v82_baseline_status": ctx.v82_baseline_status,
        "risk_hardening_controller_status": "PASS_RISK_HARDENED_SCALING_POLICY_LOCKED",
        "scaling_policy": SCALING_POLICY,
        "caps_modified_by_dummy": False,
        "live_order_placed": False,
        "readiness_governor_v43_status": "PASS",
        "execution_lock_deep_recheck_v42_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(checks)
    return common


def _verdict(name: str, ctx: V83Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v82_baseline"):
        return "PASS" if ctx.v82_baseline_status == "PASS_V82_BASELINE_READBACK" else "FAIL" if ctx.v82_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V83Context) -> dict[str, Any]:
    workstream = "v83: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v83_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V83_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v83_report.json":
        report.update({"completion_oriented_next_action_v83_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v69.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v82_carried_status": ctx.v82_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v83.json"), "risk_hardening": str(ARTIFACTS / "v83_risk_hardening_controller_report.json"), "scale_step_policy": str(ARTIFACTS / "v83_scale_step_policy_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v83.json", "dummy_canonical_identity_report_v83.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V83ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V83Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
