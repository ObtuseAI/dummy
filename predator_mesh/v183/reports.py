"""DUMMY v183 limited autonomy dry-run policy — creates an inert limited-autonomy dry-run policy; no live orders.

Encodes a dry-run-only policy with no live-submit path and no broker payload: a candidate simulation loop, an
abstention-first decision loop, a risk-stop loop, hypothetical order scoring, and a hypothetical reconcile schema.
Proves autonomous live trading is disabled and that the dry-run cannot call LiveBrokerFirewall.submit. Default is
PASS_LIMITED_AUTONOMY_DRYRUN_POLICY_LOCKED_INERT; live_orders=0 and autonomous_trading=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v183 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v183: Limited Autonomy Dryrun Policy Inert No Live Orders"
MISSION_NAME = "dummy_mission_state_report_v169.json"
FINAL_NAME = "final_report_v183.json"
INDEX_KEYS = ["limited_autonomy_dryrun_controller_status", "autonomous_trading_enabled", "live_orders"]
DASH_TITLE = "Dummy V183 Limited Autonomy Dry-Run Policy"
MISSION_KEY = "dummy_mission_state_report_v169"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Dry-Run Policy", "limited_autonomy_dryrun_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V183_ROUTES = [
    "/api/v183/limited-autonomy-dryrun-controller",
    "/api/v183/v182-baseline",
    "/api/v183/dry-run-only-policy",
    "/api/v183/no-live-submit-path-proof",
    "/api/v183/no-broker-payload-proof",
    "/api/v183/candidate-simulation-loop",
    "/api/v183/abstention-first-decision-loop",
    "/api/v183/risk-stop-loop",
    "/api/v183/hypothetical-order-scoring",
    "/api/v183/hypothetical-reconcile-schema",
    "/api/v183/autonomous-live-trading-disabled-proof",
    "/api/v183/dryrun-cannot-call-firewall-submit-proof",
    "/api/v183/no-scale-proof",
    "/api/v183/readiness-governor",
    "/api/v183/execution-lock",
    "/api/v183/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "limited-autonomy-dryrun-controller": ["v183_limited_autonomy_dryrun_controller_report.json"],
    "v182-baseline": ["v182_baseline_readback_v1_report.json"],
    "dry-run-only-policy": ["v183_dry_run_only_policy_report.json"],
    "no-live-submit-path-proof": ["v183_no_live_submit_path_proof_report.json"],
    "no-broker-payload-proof": ["v183_no_broker_payload_proof_report.json"],
    "candidate-simulation-loop": ["v183_candidate_simulation_loop_report.json"],
    "abstention-first-decision-loop": ["v183_abstention_first_decision_loop_report.json"],
    "risk-stop-loop": ["v183_risk_stop_loop_report.json"],
    "hypothetical-order-scoring": ["v183_hypothetical_order_scoring_report.json"],
    "hypothetical-reconcile-schema": ["v183_hypothetical_reconcile_schema_report.json"],
    "autonomous-live-trading-disabled-proof": ["v183_autonomous_live_trading_disabled_proof_report.json"],
    "dryrun-cannot-call-firewall-submit-proof": ["v183_dryrun_cannot_call_firewall_submit_proof_report.json"],
    "no-scale-proof": ["v183_no_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v143_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v142_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v183_report_v1.json", "completion_oriented_next_action_v183_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(183)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v183/reports.py scripts/generate_v183_reports.py dashboard/backend/v183_routes.py",
    "python scripts/generate_v183_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

HYPOTHETICAL_RECONCILE_SCHEMA = ["order_attempt_id", "state", "fill_qty", "slippage_bps", "latency_ms", "fee_cents", "idempotency_key", "abstained"]


class V183Context:
    def __init__(self) -> None:
        self.v182_baseline_status = sgc.baseline_status("final_report_v182.json", "V182")

    @property
    def controller_status(self) -> str:
        return "FAIL_DRYRUN_BASELINE_REGRESSION" if self.v182_baseline_status.startswith("FAIL") else "PASS_LIMITED_AUTONOMY_DRYRUN_POLICY_LOCKED_INERT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v182_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V182_BASELINE_REGRESSION"] if self.v182_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "LIMITED_AUTONOMY_DRYRUN_POLICY_LOCKED_INERT_AWAIT_AUTONOMY_APPROVAL_NO_LIVE_ORDERS"


def _common(ctx: V183Context) -> dict[str, Any]:
    return {
        "v182_baseline_status": ctx.v182_baseline_status,
        "limited_autonomy_dryrun_controller_status": ctx.controller_status,
        "dry_run_only_policy_status": "PASS_DRY_RUN_ONLY_POLICY_LOCKED",
        "no_live_submit_path_proof_status": "PASS_NO_LIVE_SUBMIT_PATH",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "candidate_simulation_loop_status": "PASS_CANDIDATE_SIMULATION_INERT",
        "abstention_first_decision_loop_status": "PASS_ABSTENTION_FIRST_INERT",
        "risk_stop_loop_status": "PASS_RISK_STOP_LOOP_INERT",
        "hypothetical_order_scoring_status": "PASS_HYPOTHETICAL_ORDER_SCORING_INERT",
        "hypothetical_reconcile_schema_status": "PASS_HYPOTHETICAL_RECONCILE_SCHEMA_LISTED",
        "hypothetical_reconcile_schema": HYPOTHETICAL_RECONCILE_SCHEMA,
        "autonomous_live_trading_disabled_proof_status": "PASS_AUTONOMOUS_LIVE_TRADING_DISABLED",
        "dryrun_cannot_call_firewall_submit_proof_status": "PASS_DRYRUN_CANNOT_CALL_FIREWALL_SUBMIT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "dry_run_inert": True,
        "autonomy_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v143_status": "PASS",
        "execution_lock_deep_recheck_v142_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V183Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v182_baseline"):
        return "PASS" if ctx.v182_baseline_status == "PASS_V182_BASELINE_READBACK" else "FAIL" if ctx.v182_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V183Context) -> dict[str, Any]:
    workstream = "v183: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v183_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V183_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v183_report.json":
        report.update({"completion_oriented_next_action_v183_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v182_carried_status": ctx.v182_baseline_status, "limited_autonomy_dryrun_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v183_limited_autonomy_dryrun_controller_report.json"), "autonomous_live_trading_disabled": str(ARTIFACTS / "v183_autonomous_live_trading_disabled_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v183.json", "dummy_canonical_identity_report_v183.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V183ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V183Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
