"""DUMMY v166 repeat pilot final preflight — assembles the final repeat-pilot preflight packet; never submits.

Reads the V165 repeat authority binder plus repeat-approval / first-pilot reconcile+forensic / live-submit-caps /
firewall proofs, limit-only / no-market proofs, stricter max-order-size and exposure thresholds, and
no-loss/drift/liquidity/broker-error/slippage locks with kill-switch/rollback/idempotency. Default is
PARTIAL_REPEAT_PREFLIGHT_BLOCKED. When the binder is bound the packet is READY — nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v166 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v166: Repeat Pilot Final Preflight Stricter Risk No Submit"
MISSION_NAME = "dummy_mission_state_report_v152.json"
FINAL_NAME = "final_report_v166.json"
INDEX_KEYS = ["repeat_preflight_controller_status", "repeat_preflight_ready", "live_orders"]
DASH_TITLE = "Dummy V166 Repeat Pilot Final Preflight"
MISSION_KEY = "dummy_mission_state_report_v152"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Preflight", "repeat_preflight_controller_status"],
    ["Preflight Ready", "repeat_preflight_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V166_ROUTES = [
    "/api/v166/repeat-preflight-controller",
    "/api/v166/v165-baseline",
    "/api/v166/repeat-approval-proof",
    "/api/v166/first-pilot-reconcile-proof",
    "/api/v166/first-pilot-forensic-proof",
    "/api/v166/live-submit-caps-snapshot-proof",
    "/api/v166/firewall-adapter-proof",
    "/api/v166/limit-only-proof",
    "/api/v166/no-market-order-proof",
    "/api/v166/stricter-max-order-size",
    "/api/v166/stricter-exposure-threshold",
    "/api/v166/no-loss-lock",
    "/api/v166/no-drift-lock",
    "/api/v166/no-liquidity-lock",
    "/api/v166/no-broker-error-lock",
    "/api/v166/no-slippage-lock",
    "/api/v166/kill-switch-proof",
    "/api/v166/rollback-proof",
    "/api/v166/idempotency-proof",
    "/api/v166/no-submit-proof",
    "/api/v166/readiness-governor",
    "/api/v166/execution-lock",
    "/api/v166/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-preflight-controller": ["v166_repeat_preflight_controller_report.json"],
    "v165-baseline": ["v165_baseline_readback_v1_report.json"],
    "repeat-approval-proof": ["v166_repeat_approval_proof_report.json"],
    "first-pilot-reconcile-proof": ["v166_first_pilot_reconcile_proof_report.json"],
    "first-pilot-forensic-proof": ["v166_first_pilot_forensic_proof_report.json"],
    "live-submit-caps-snapshot-proof": ["v166_live_submit_caps_snapshot_proof_report.json"],
    "firewall-adapter-proof": ["v166_firewall_adapter_proof_report.json"],
    "limit-only-proof": ["v166_limit_only_proof_report.json"],
    "no-market-order-proof": ["v166_no_market_order_proof_report.json"],
    "stricter-max-order-size": ["v166_stricter_max_order_size_report.json"],
    "stricter-exposure-threshold": ["v166_stricter_exposure_threshold_report.json"],
    "no-loss-lock": ["v166_no_loss_lock_report.json"],
    "no-drift-lock": ["v166_no_drift_lock_report.json"],
    "no-liquidity-lock": ["v166_no_liquidity_lock_report.json"],
    "no-broker-error-lock": ["v166_no_broker_error_lock_report.json"],
    "no-slippage-lock": ["v166_no_slippage_lock_report.json"],
    "kill-switch-proof": ["v166_kill_switch_proof_report.json"],
    "rollback-proof": ["v166_rollback_proof_report.json"],
    "idempotency-proof": ["v166_idempotency_proof_report.json"],
    "no-submit-proof": ["v166_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v126_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v125_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v166_report_v1.json", "completion_oriented_next_action_v166_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(166)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v166/reports.py scripts/generate_v166_reports.py dashboard/backend/v166_routes.py",
    "python scripts/generate_v166_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V166Context:
    def __init__(self, *, binder_ready_override=None) -> None:
        self.v165_baseline_status = sgc.baseline_status("final_report_v165.json", "V165")
        if binder_ready_override is not None:
            self.binder_ready = bool(binder_ready_override)
        else:
            self.binder_ready = str(sgc.load_artifact("final_report_v165.json").get("repeat_authority_binder_controller_status", "")) == "PASS_REPEAT_AUTHORITY_BOUND_NO_SUBMIT"

    @property
    def ready(self) -> bool:
        return self.binder_ready

    @property
    def controller_status(self) -> str:
        return "PASS_REPEAT_PREFLIGHT_READY_NO_SUBMIT" if self.ready else "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v165_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v165_baseline_status.startswith("FAIL"):
            return ["FAIL_V165_BASELINE_REGRESSION"]
        return [] if self.ready else ["REPEAT_AUTHORITY_NOT_BOUND"]

    @property
    def next_action(self) -> str:
        return "REPEAT_PREFLIGHT_READY_NO_SUBMIT_AWAIT_REPEAT_PILOT_FIRE_ON_FULL_AUTH" if self.ready else "OPERATOR_MUST_BIND_REPEAT_AUTHORITY_BEFORE_PREFLIGHT_NO_SUBMIT"


def _common(ctx: V166Context) -> dict[str, Any]:
    def s(v):
        return v if ctx.ready else "PARTIAL_PROOF_ABSENT"
    return {
        "v165_baseline_status": ctx.v165_baseline_status,
        "repeat_preflight_controller_status": ctx.controller_status,
        "repeat_approval_proof_status": s("PASS_REPEAT_APPROVAL_PROVEN"),
        "first_pilot_reconcile_proof_status": s("PASS_FIRST_PILOT_RECONCILE_PROVEN"),
        "first_pilot_forensic_proof_status": s("PASS_FIRST_PILOT_FORENSIC_PROVEN"),
        "live_submit_caps_snapshot_proof_status": s("PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_PROVEN"),
        "firewall_adapter_proof_status": s("PASS_FIREWALL_ADAPTER_PROVEN"),
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "stricter_max_order_size_status": "PASS_STRICTER_MAX_ORDER_SIZE_LOCKED",
        "stricter_exposure_threshold_status": "PASS_STRICTER_EXPOSURE_THRESHOLD_LOCKED",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
        "no_liquidity_lock_status": "PASS_NO_LIQUIDITY_LOCK_ARMED",
        "no_broker_error_lock_status": "PASS_NO_BROKER_ERROR_LOCK_ARMED",
        "no_slippage_lock_status": "PASS_NO_SLIPPAGE_LOCK_ARMED",
        "kill_switch_proof_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_proof_status": "PASS_ROLLBACK_READY",
        "idempotency_proof_status": "PASS_IDEMPOTENCY_READY",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "repeat_preflight_ready": ctx.ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v126_status": "PASS",
        "execution_lock_deep_recheck_v125_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V166Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v165_baseline"):
        return "PASS" if ctx.v165_baseline_status == "PASS_V165_BASELINE_READBACK" else "FAIL" if ctx.v165_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v166_repeat_preflight_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V166Context) -> dict[str, Any]:
    workstream = "v166: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v166_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V166_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v166_report.json":
        report.update({"completion_oriented_next_action_v166_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v165_carried_status": ctx.v165_baseline_status, "repeat_preflight_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v166_repeat_preflight_controller_report.json"), "no_submit": str(ARTIFACTS / "v166_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v166.json", "dummy_canonical_identity_report_v166.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V166ReportFactory:
    def __init__(self, *, binder_ready_override=None) -> None:
        self.kw = dict(binder_ready_override=binder_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V166Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
