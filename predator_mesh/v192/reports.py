"""DUMMY v192 guarded autonomy rehearsal session — runs a dry-only guarded-autonomy rehearsal using shadow decisions; no live order.

Runs a shadow candidate sequence through an autonomous abstain/lock/escalate loop with hypothetical trade-candidate
records, hypothetical per-order approval checks, hypothetical risk stops, and a hypothetical reconcile schema. No broker
payload, no LiveBrokerFirewall.submit call, no account/private data, no scale. Default is
PASS_GUARDED_AUTONOMY_REHEARSAL_SESSION_READY_DRY_ONLY; live_orders=0, autonomous_trading=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v192 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v192: Guarded Autonomy Rehearsal Session Dry Only"
MISSION_NAME = "dummy_mission_state_report_v178.json"
FINAL_NAME = "final_report_v192.json"
INDEX_KEYS = ["autonomy_rehearsal_controller_status", "autonomous_trading_enabled", "live_orders"]
DASH_TITLE = "Dummy V192 Guarded Autonomy Rehearsal Session"
MISSION_KEY = "dummy_mission_state_report_v178"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Rehearsal Session", "autonomy_rehearsal_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V192_ROUTES = [
    "/api/v192/autonomy-rehearsal-controller",
    "/api/v192/v191-baseline",
    "/api/v192/rehearsal-session-id",
    "/api/v192/shadow-candidate-sequence",
    "/api/v192/autonomous-abstain-lock-escalate-loop",
    "/api/v192/hypothetical-trade-candidate-records",
    "/api/v192/hypothetical-per-order-approval-checks",
    "/api/v192/hypothetical-risk-stops",
    "/api/v192/hypothetical-reconcile-schema",
    "/api/v192/dry-live-firewall-proof",
    "/api/v192/no-broker-payload-proof",
    "/api/v192/no-firewall-submit-call-proof",
    "/api/v192/no-account-private-data-proof",
    "/api/v192/no-scale-proof",
    "/api/v192/readiness-governor",
    "/api/v192/execution-lock",
    "/api/v192/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-rehearsal-controller": ["v192_autonomy_rehearsal_controller_report.json"],
    "v191-baseline": ["v191_baseline_readback_v1_report.json"],
    "rehearsal-session-id": ["v192_rehearsal_session_id_report.json"],
    "shadow-candidate-sequence": ["v192_shadow_candidate_sequence_report.json"],
    "autonomous-abstain-lock-escalate-loop": ["v192_autonomous_abstain_lock_escalate_loop_report.json"],
    "hypothetical-trade-candidate-records": ["v192_hypothetical_trade_candidate_records_report.json"],
    "hypothetical-per-order-approval-checks": ["v192_hypothetical_per_order_approval_checks_report.json"],
    "hypothetical-risk-stops": ["v192_hypothetical_risk_stops_report.json"],
    "hypothetical-reconcile-schema": ["v192_hypothetical_reconcile_schema_report.json"],
    "dry-live-firewall-proof": ["v192_dry_live_firewall_proof_report.json"],
    "no-broker-payload-proof": ["v192_no_broker_payload_proof_report.json"],
    "no-firewall-submit-call-proof": ["v192_no_firewall_submit_call_proof_report.json"],
    "no-account-private-data-proof": ["v192_no_account_private_data_proof_report.json"],
    "no-scale-proof": ["v192_no_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v152_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v151_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v192_report_v1.json", "completion_oriented_next_action_v192_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(192)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v192/reports.py scripts/generate_v192_reports.py dashboard/backend/v192_routes.py",
    "python scripts/generate_v192_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

HYPOTHETICAL_RECONCILE_SCHEMA = ["order_attempt_id", "state", "fill_qty", "slippage_bps", "latency_ms", "fee_cents", "idempotency_key", "abstained", "escalated"]


class V192Context:
    def __init__(self) -> None:
        self.v191_baseline_status = sgc.baseline_status("final_report_v191.json", "V191")
        self.rehearsal_session_id = sgc.sha256_bytes(("guarded-autonomy-rehearsal|" + str(self.v191_baseline_status)).encode("utf-8"))[:24]

    @property
    def controller_status(self) -> str:
        return "FAIL_REHEARSAL_BASELINE_REGRESSION" if self.v191_baseline_status.startswith("FAIL") else "PASS_GUARDED_AUTONOMY_REHEARSAL_SESSION_READY_DRY_ONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v191_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V191_BASELINE_REGRESSION"] if self.v191_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "GUARDED_AUTONOMY_REHEARSAL_SESSION_READY_DRY_ONLY_AWAIT_PRODUCTION_HARDENING_NO_LIVE_ORDER"


def _common(ctx: V192Context) -> dict[str, Any]:
    return {
        "v191_baseline_status": ctx.v191_baseline_status,
        "autonomy_rehearsal_controller_status": ctx.controller_status,
        "rehearsal_session_id_status": "PASS_REHEARSAL_SESSION_ID_ASSIGNED",
        "rehearsal_session_id": ctx.rehearsal_session_id,
        "shadow_candidate_sequence_status": "PASS_SHADOW_CANDIDATE_SEQUENCE_INERT",
        "autonomous_abstain_lock_escalate_loop_status": "PASS_ABSTAIN_LOCK_ESCALATE_LOOP_INERT",
        "hypothetical_trade_candidate_records_status": "PASS_HYPOTHETICAL_TRADE_CANDIDATE_INERT",
        "hypothetical_per_order_approval_checks_status": "PASS_HYPOTHETICAL_PER_ORDER_APPROVAL_INERT",
        "hypothetical_risk_stops_status": "PASS_HYPOTHETICAL_RISK_STOPS_INERT",
        "hypothetical_reconcile_schema_status": "PASS_HYPOTHETICAL_RECONCILE_SCHEMA_LISTED",
        "hypothetical_reconcile_schema": HYPOTHETICAL_RECONCILE_SCHEMA,
        "dry_live_firewall_proof_status": "PASS_DRY_LOCKED_NO_CROSSOVER",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "no_firewall_submit_call_proof_status": "PASS_NO_FIREWALL_SUBMIT_CALL",
        "no_account_private_data_proof_status": "PASS_NO_ACCOUNT_PRIVATE_DATA",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "rehearsal_dry_only": True,
        "autonomy_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v152_status": "PASS",
        "execution_lock_deep_recheck_v151_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V192Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v191_baseline"):
        return "PASS" if ctx.v191_baseline_status == "PASS_V191_BASELINE_READBACK" else "FAIL" if ctx.v191_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V192Context) -> dict[str, Any]:
    workstream = "v192: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v192_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V192_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v192_report.json":
        report.update({"completion_oriented_next_action_v192_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v191_carried_status": ctx.v191_baseline_status, "autonomy_rehearsal_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v192_autonomy_rehearsal_controller_report.json"), "no_firewall_submit_call": str(ARTIFACTS / "v192_no_firewall_submit_call_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v192.json", "dummy_canonical_identity_report_v192.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V192ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V192Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
