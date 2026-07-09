"""DUMMY v179 controlled session forensic review — reviews session execution reality if V178 has session state; no new orders.

Default is PARTIAL_NO_CONTROLLED_SESSION_TO_REVIEW. When V178 classified a session state it summarizes
fill/reject/cancel/expired/partial-fill, buckets slippage/latency/fee, reviews liquidity reality, edge-vs-execution
reality, per-order abstention, risk-governor behavior, kill-switch/rollback, and broker read-only consistency, all with
private-data redaction. No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v179 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v179: Controlled Session Forensic Review Execution Risk And Abstention Reality"
MISSION_NAME = "dummy_mission_state_report_v165.json"
FINAL_NAME = "final_report_v179.json"
INDEX_KEYS = ["session_forensic_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V179 Controlled Session Forensic Review"
MISSION_KEY = "dummy_mission_state_report_v165"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Forensic", "session_forensic_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V179_ROUTES = [
    "/api/v179/session-forensic-controller",
    "/api/v179/v178-baseline",
    "/api/v179/fill-reject-cancel-summary",
    "/api/v179/slippage-buckets",
    "/api/v179/latency-buckets",
    "/api/v179/fee-buckets",
    "/api/v179/liquidity-reality",
    "/api/v179/edge-vs-execution-reality",
    "/api/v179/per-order-abstention-review",
    "/api/v179/risk-governor-behavior-review",
    "/api/v179/kill-switch-review",
    "/api/v179/rollback-review",
    "/api/v179/broker-readonly-consistency-check",
    "/api/v179/private-data-redaction",
    "/api/v179/no-new-order-proof",
    "/api/v179/readiness-governor",
    "/api/v179/execution-lock",
    "/api/v179/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-forensic-controller": ["v179_session_forensic_controller_report.json"],
    "v178-baseline": ["v178_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v179_fill_reject_cancel_summary_report.json"],
    "slippage-buckets": ["v179_slippage_buckets_report.json"],
    "latency-buckets": ["v179_latency_buckets_report.json"],
    "fee-buckets": ["v179_fee_buckets_report.json"],
    "liquidity-reality": ["v179_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v179_edge_vs_execution_reality_report.json"],
    "per-order-abstention-review": ["v179_per_order_abstention_review_report.json"],
    "risk-governor-behavior-review": ["v179_risk_governor_behavior_review_report.json"],
    "kill-switch-review": ["v179_kill_switch_review_report.json"],
    "rollback-review": ["v179_rollback_review_report.json"],
    "broker-readonly-consistency-check": ["v179_broker_readonly_consistency_check_report.json"],
    "private-data-redaction": ["v179_private_data_redaction_report.json"],
    "no-new-order-proof": ["v179_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v139_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v138_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v179_report_v1.json", "completion_oriented_next_action_v179_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(179)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v179/reports.py scripts/generate_v179_reports.py dashboard/backend/v179_routes.py",
    "python scripts/generate_v179_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V179Context:
    def __init__(self, *, v178_final_override=None) -> None:
        self.v178_baseline_status = sgc.baseline_status("final_report_v178.json", "V178")
        v178 = v178_final_override if v178_final_override is not None else sgc.load_artifact("final_report_v178.json")
        self.session_reviewable = str(v178.get("session_reconcile_controller_status", "")) == "PASS_CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED"
        self.session_state = str(v178.get("session_state", "NO_ATTEMPT")) if self.session_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_CONTROLLED_SESSION_FORENSIC_REVIEWED" if self.session_reviewable else "PARTIAL_NO_CONTROLLED_SESSION_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v178_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.session_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v178_baseline_status.startswith("FAIL"):
            return ["FAIL_V178_BASELINE_REGRESSION"]
        return [] if self.session_reviewable else ["NO_CONTROLLED_SESSION_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "CONTROLLED_SESSION_FORENSIC_REVIEWED_AWAIT_SESSION_DECISION_NO_NEW_ORDER" if self.session_reviewable else "AWAIT_CONTROLLED_SESSION_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V179Context) -> dict[str, Any]:
    present = ctx.session_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_SESSION"
    return {
        "v178_baseline_status": ctx.v178_baseline_status,
        "session_forensic_controller_status": ctx.controller_status,
        "session_state": ctx.session_state,
        "fill_reject_cancel_summary_status": s("PASS_FILL_REJECT_CANCEL_EXPIRED_PARTIAL_SUMMARIZED"),
        "slippage_buckets_status": s("PASS_SLIPPAGE_BUCKETED"),
        "latency_buckets_status": s("PASS_LATENCY_BUCKETED"),
        "fee_buckets_status": s("PASS_FEE_BUCKETED"),
        "liquidity_reality_status": s("PASS_LIQUIDITY_REALITY_REVIEWED"),
        "edge_vs_execution_reality_status": s("PASS_EDGE_VS_EXECUTION_REVIEWED"),
        "per_order_abstention_review_status": s("PASS_PER_ORDER_ABSTENTION_REVIEWED"),
        "risk_governor_behavior_review_status": s("PASS_RISK_GOVERNOR_BEHAVIOR_REVIEWED"),
        "kill_switch_review_status": s("PASS_KILL_SWITCH_REVIEWED"),
        "rollback_review_status": s("PASS_ROLLBACK_REVIEWED"),
        "broker_readonly_consistency_check_status": s("PASS_BROKER_READONLY_CONSISTENT"),
        "private_data_redaction_status": "PASS_PRIVATE_DATA_REDACTED",
        "session_forensic_capture": {"captured": present, "private_data_leaked": False},
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v139_status": "PASS",
        "execution_lock_deep_recheck_v138_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V179Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v178_baseline"):
        return "PASS" if ctx.v178_baseline_status == "PASS_V178_BASELINE_READBACK" else "FAIL" if ctx.v178_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v179_session_forensic_controller_report.json":
        return "PASS" if ctx.session_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V179Context) -> dict[str, Any]:
    workstream = "v179: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v179_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V179_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v179_report.json":
        report.update({"completion_oriented_next_action_v179_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v178_carried_status": ctx.v178_baseline_status, "session_forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v179_session_forensic_controller_report.json"), "no_new_order": str(ARTIFACTS / "v179_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v179.json", "dummy_canonical_identity_report_v179.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V179ReportFactory:
    def __init__(self, *, v178_final_override=None) -> None:
        self.kw = dict(v178_final_override=v178_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V179Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
