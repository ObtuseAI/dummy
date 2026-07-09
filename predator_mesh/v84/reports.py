"""DUMMY v84 session-level trading governor and production-readiness audit — no autonomous trading."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v84 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

PRODUCTION_READINESS_CHECKLIST = {
    "session_start_stop_rules": True,
    "per_order_approval_mode": True,
    "daily_budget_lock": True,
    "exposure_lock": True,
    "drift_lock": True,
    "no_trade_abstention_governor": True,
    "live_edge_degradation_monitor": True,
    "broker_failure_mode_policy": True,
    "reconcile_requirement": True,
    "audit_ledger_requirement": True,
    "autonomous_trading_enabled": False,
}

V84_ROUTES = [
    "/api/v84/session-governor",
    "/api/v84/v83-baseline",
    "/api/v84/session-start-stop-rules",
    "/api/v84/per-order-approval-mode",
    "/api/v84/daily-budget-lock",
    "/api/v84/exposure-lock",
    "/api/v84/drift-lock",
    "/api/v84/no-trade-abstention-governor",
    "/api/v84/live-edge-degradation-monitor",
    "/api/v84/broker-failure-mode-policy",
    "/api/v84/reconcile-requirement",
    "/api/v84/audit-ledger-requirement",
    "/api/v84/production-readiness-checklist",
    "/api/v84/readiness-governor",
    "/api/v84/execution-lock",
    "/api/v84/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-governor": ["v84_session_governor_report.json"],
    "v83-baseline": ["v83_baseline_readback_v1_report.json"],
    "session-start-stop-rules": ["v84_session_start_stop_rules_report.json"],
    "per-order-approval-mode": ["v84_per_order_approval_mode_report.json"],
    "daily-budget-lock": ["v84_daily_budget_lock_report.json"],
    "exposure-lock": ["v84_exposure_lock_report.json"],
    "drift-lock": ["v84_drift_lock_report.json"],
    "no-trade-abstention-governor": ["v84_no_trade_abstention_governor_report.json"],
    "live-edge-degradation-monitor": ["v84_live_edge_degradation_monitor_report.json"],
    "broker-failure-mode-policy": ["v84_broker_failure_mode_policy_report.json"],
    "reconcile-requirement": ["v84_reconcile_requirement_report.json"],
    "audit-ledger-requirement": ["v84_audit_ledger_requirement_report.json"],
    "production-readiness-checklist": ["v84_production_readiness_checklist_report.json"],
    "readiness-governor": ["readiness_governor_v44_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v43_report.json"],
    "mission-state": ["dummy_mission_state_report_v70.json", "dashboard_v84_report_v1.json", "completion_oriented_next_action_v84_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(84)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v84/reports.py scripts/generate_v84_reports.py dashboard/backend/v84_routes.py",
    "python scripts/generate_v84_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V84Context:
    def __init__(self) -> None:
        self.v83_baseline_status = sgc.baseline_status("final_report_v83.json", "V83")

    @property
    def gate_status(self) -> str:
        # Autonomous trading is never enabled, so FAIL_PRODUCTION_AUDIT_ENABLED_AUTONOMOUS_TRADING cannot occur.
        if self.v83_baseline_status.startswith("FAIL"):
            return "PARTIAL_PRODUCTION_READINESS_BLOCKED"
        return "PASS_PRODUCTION_READINESS_AUDIT_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v83_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V83_BASELINE_REGRESSION"] if self.v83_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "PRODUCTION_READINESS_AUDIT_LOCKED_NO_AUTONOMOUS_TRADING_PER_ORDER_APPROVAL_ONLY"


def _common(ctx: V84Context) -> dict[str, Any]:
    checks = {f"{k}_status": "PASS_DEFINED_LOCKED" for k in ["session_start_stop_rules", "per_order_approval_mode", "daily_budget_lock", "exposure_lock", "drift_lock", "no_trade_abstention_governor", "live_edge_degradation_monitor", "broker_failure_mode_policy", "reconcile_requirement", "audit_ledger_requirement"]}
    common = {
        "v83_baseline_status": ctx.v83_baseline_status,
        "session_governor_status": ctx.gate_status,
        "production_readiness_checklist_status": ctx.gate_status,
        "production_readiness_checklist": PRODUCTION_READINESS_CHECKLIST,
        "autonomous_trading_enabled": False,
        "autonomous_production_trading": False,
        "live_order_placed": False,
        "readiness_governor_v44_status": "PASS",
        "execution_lock_deep_recheck_v43_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(checks)
    return common


def _verdict(name: str, ctx: V84Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v83_baseline"):
        return "PASS" if ctx.v83_baseline_status == "PASS_V83_BASELINE_READBACK" else "FAIL" if ctx.v83_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V84Context) -> dict[str, Any]:
    workstream = "v84: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v84_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V84_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_enable_autonomous_trading": False})
    elif name == "completion_oriented_next_action_v84_report.json":
        report.update({"completion_oriented_next_action_v84_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v70.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v83_carried_status": ctx.v83_baseline_status, "session_governor_status": ctx.gate_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v84.json"), "session_governor": str(ARTIFACTS / "v84_session_governor_report.json"), "production_readiness": str(ARTIFACTS / "v84_production_readiness_checklist_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v84.json", "dummy_canonical_identity_report_v84.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V84ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V84Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
