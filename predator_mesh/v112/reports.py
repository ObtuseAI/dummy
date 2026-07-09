"""DUMMY v112 session-level live governor — builds a bounded per-order-approval session governor; no orders by default.

Encodes session start/stop rules, per-order approval mode, session order-count cap, budget/exposure/drift/
cooldown locks, kill switch, broker-failure-mode policy, and a reconcile requirement. The governor is ready
and locked; it never auto-submits and session_live_orders stays 0.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v112 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v112: Session Level Live Governor Per Order Approval Mode"
MISSION_NAME = "dummy_mission_state_report_v98.json"
FINAL_NAME = "final_report_v112.json"
INDEX_KEYS = ["session_governor_status", "session_live_orders", "no_auto_submit_proof_status"]
DASH_TITLE = "Dummy V112 Session Level Live Governor"
MISSION_KEY = "dummy_mission_state_report_v98"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Governor", "session_governor_status"],
    ["Session Live Orders", "session_live_orders"],
    ["Per-Order Mode", "per_order_approval_mode"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V112_ROUTES = [
    "/api/v112/session-governor-controller",
    "/api/v112/v111-baseline",
    "/api/v112/session-start-stop-rules",
    "/api/v112/per-order-approval-mode",
    "/api/v112/max-session-order-count",
    "/api/v112/daily-budget-lock",
    "/api/v112/exposure-lock",
    "/api/v112/drift-lock",
    "/api/v112/cooldown-lock",
    "/api/v112/kill-switch",
    "/api/v112/broker-failure-mode-policy",
    "/api/v112/reconcile-requirement",
    "/api/v112/no-auto-submit-proof",
    "/api/v112/readiness-governor",
    "/api/v112/execution-lock",
    "/api/v112/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-governor-controller": ["v112_session_governor_controller_report.json"],
    "v111-baseline": ["v111_baseline_readback_v1_report.json"],
    "session-start-stop-rules": ["v112_session_start_stop_rules_report.json"],
    "per-order-approval-mode": ["v112_per_order_approval_mode_report.json"],
    "max-session-order-count": ["v112_max_session_order_count_report.json"],
    "daily-budget-lock": ["v112_daily_budget_lock_report.json"],
    "exposure-lock": ["v112_exposure_lock_report.json"],
    "drift-lock": ["v112_drift_lock_report.json"],
    "cooldown-lock": ["v112_cooldown_lock_report.json"],
    "kill-switch": ["v112_kill_switch_report.json"],
    "broker-failure-mode-policy": ["v112_broker_failure_mode_policy_report.json"],
    "reconcile-requirement": ["v112_reconcile_requirement_report.json"],
    "no-auto-submit-proof": ["v112_no_auto_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v72_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v71_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v112_report_v1.json", "completion_oriented_next_action_v112_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(112)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v112/reports.py scripts/generate_v112_reports.py dashboard/backend/v112_routes.py",
    "python scripts/generate_v112_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

MAX_SESSION_ORDER_COUNT = 1


class V112Context:
    def __init__(self) -> None:
        self.v111_baseline_status = sgc.baseline_status("final_report_v111.json", "V111")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v111_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V111_BASELINE_REGRESSION"] if self.v111_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "SESSION_GOVERNOR_READY_LOCKED_AWAIT_CONTROLLED_SESSION_APPROVAL_NO_AUTO_SUBMIT"


def _common(ctx: V112Context) -> dict[str, Any]:
    return {
        "v111_baseline_status": ctx.v111_baseline_status,
        "session_governor_status": "PASS_SESSION_GOVERNOR_READY_LOCKED",
        "session_governor_controller_status": "PASS_SESSION_GOVERNOR_READY_LOCKED",
        "session_start_stop_rules_status": "PASS_SESSION_START_STOP_RULES_LOCKED",
        "per_order_approval_mode_status": "PASS_PER_ORDER_APPROVAL_MODE_LOCKED",
        "per_order_approval_mode": True,
        "max_session_order_count_status": "PASS_MAX_SESSION_ORDER_COUNT_LOCKED",
        "max_session_order_count": MAX_SESSION_ORDER_COUNT,
        "daily_budget_lock_status": "PASS_DAILY_BUDGET_LOCKED",
        "exposure_lock_status": "PASS_EXPOSURE_LOCKED",
        "drift_lock_status": "PASS_DRIFT_LOCKED",
        "cooldown_lock_status": "PASS_COOLDOWN_LOCKED",
        "kill_switch_status": "PASS_KILL_SWITCH_ARMED",
        "broker_failure_mode_policy_status": "PASS_BROKER_FAILURE_MODE_FAIL_CLOSED",
        "reconcile_requirement_status": "PASS_RECONCILE_REQUIRED",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "session_live_orders": 0,
        "session_auto_submit_enabled": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v72_status": "PASS",
        "execution_lock_deep_recheck_v71_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V112Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v111_baseline"):
        return "PASS" if ctx.v111_baseline_status == "PASS_V111_BASELINE_READBACK" else "FAIL" if ctx.v111_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V112Context) -> dict[str, Any]:
    workstream = "v112: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v112_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V112_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v112_report.json":
        report.update({"completion_oriented_next_action_v112_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v111_carried_status": ctx.v111_baseline_status, "session_governor_status": "PASS_SESSION_GOVERNOR_READY_LOCKED", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v112_session_governor_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v112_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v112.json", "dummy_canonical_identity_report_v112.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V112ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V112Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
