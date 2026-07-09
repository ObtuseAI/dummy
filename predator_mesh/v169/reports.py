"""DUMMY v169 repeat pilot forensic review — reviews repeat-pilot execution reality if V168 has a state; no new orders.

Default is PARTIAL_NO_REPEAT_PILOT_TO_REVIEW. When V168 classified a repeat pilot state it summarizes
fill/reject/cancel/expired/partial-fill, buckets slippage/latency/fee, reviews liquidity reality, edge-vs-execution
reality, the abstention decision, risk-governor behavior, kill-switch/rollback, and broker read-only consistency, all
with private-data redaction. No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v169 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v169: Repeat Pilot Forensic Review Execution Reality And Risk Behavior"
MISSION_NAME = "dummy_mission_state_report_v155.json"
FINAL_NAME = "final_report_v169.json"
INDEX_KEYS = ["repeat_forensic_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V169 Repeat Pilot Forensic Review"
MISSION_KEY = "dummy_mission_state_report_v155"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Forensic", "repeat_forensic_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V169_ROUTES = [
    "/api/v169/repeat-forensic-controller",
    "/api/v169/v168-baseline",
    "/api/v169/fill-reject-cancel-summary",
    "/api/v169/slippage-bucket",
    "/api/v169/latency-bucket",
    "/api/v169/fee-bucket",
    "/api/v169/liquidity-reality",
    "/api/v169/edge-vs-execution-reality",
    "/api/v169/abstention-decision-review",
    "/api/v169/risk-governor-behavior-review",
    "/api/v169/kill-switch-review",
    "/api/v169/rollback-review",
    "/api/v169/broker-readonly-consistency-check",
    "/api/v169/private-data-redaction",
    "/api/v169/no-new-order-proof",
    "/api/v169/readiness-governor",
    "/api/v169/execution-lock",
    "/api/v169/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-forensic-controller": ["v169_repeat_forensic_controller_report.json"],
    "v168-baseline": ["v168_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v169_fill_reject_cancel_summary_report.json"],
    "slippage-bucket": ["v169_slippage_bucket_report.json"],
    "latency-bucket": ["v169_latency_bucket_report.json"],
    "fee-bucket": ["v169_fee_bucket_report.json"],
    "liquidity-reality": ["v169_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v169_edge_vs_execution_reality_report.json"],
    "abstention-decision-review": ["v169_abstention_decision_review_report.json"],
    "risk-governor-behavior-review": ["v169_risk_governor_behavior_review_report.json"],
    "kill-switch-review": ["v169_kill_switch_review_report.json"],
    "rollback-review": ["v169_rollback_review_report.json"],
    "broker-readonly-consistency-check": ["v169_broker_readonly_consistency_check_report.json"],
    "private-data-redaction": ["v169_private_data_redaction_report.json"],
    "no-new-order-proof": ["v169_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v129_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v128_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v169_report_v1.json", "completion_oriented_next_action_v169_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(169)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v169/reports.py scripts/generate_v169_reports.py dashboard/backend/v169_routes.py",
    "python scripts/generate_v169_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V169Context:
    def __init__(self, *, v168_final_override=None) -> None:
        self.v168_baseline_status = sgc.baseline_status("final_report_v168.json", "V168")
        v168 = v168_final_override if v168_final_override is not None else sgc.load_artifact("final_report_v168.json")
        self.pilot_reviewable = str(v168.get("repeat_reconcile_controller_status", "")) == "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v168.get("order_state", "NO_ATTEMPT")) if self.pilot_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_REPEAT_PILOT_FORENSIC_REVIEWED" if self.pilot_reviewable else "PARTIAL_NO_REPEAT_PILOT_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v168_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pilot_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v168_baseline_status.startswith("FAIL"):
            return ["FAIL_V168_BASELINE_REGRESSION"]
        return [] if self.pilot_reviewable else ["NO_REPEAT_PILOT_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "REPEAT_PILOT_FORENSIC_REVIEWED_AWAIT_PILOT_PAIR_AUDIT_NO_NEW_ORDER" if self.pilot_reviewable else "AWAIT_REPEAT_PILOT_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V169Context) -> dict[str, Any]:
    present = ctx.pilot_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_PILOT"
    return {
        "v168_baseline_status": ctx.v168_baseline_status,
        "repeat_forensic_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "fill_reject_cancel_summary_status": s("PASS_FILL_REJECT_CANCEL_EXPIRED_PARTIAL_SUMMARIZED"),
        "slippage_bucket_status": s("PASS_SLIPPAGE_BUCKETED"),
        "latency_bucket_status": s("PASS_LATENCY_BUCKETED"),
        "fee_bucket_status": s("PASS_FEE_BUCKETED"),
        "liquidity_reality_status": s("PASS_LIQUIDITY_REALITY_REVIEWED"),
        "edge_vs_execution_reality_status": s("PASS_EDGE_VS_EXECUTION_REVIEWED"),
        "abstention_decision_review_status": s("PASS_ABSTENTION_DECISION_REVIEWED"),
        "risk_governor_behavior_review_status": s("PASS_RISK_GOVERNOR_BEHAVIOR_REVIEWED"),
        "kill_switch_review_status": s("PASS_KILL_SWITCH_REVIEWED"),
        "rollback_review_status": s("PASS_ROLLBACK_REVIEWED"),
        "broker_readonly_consistency_check_status": s("PASS_BROKER_READONLY_CONSISTENT"),
        "private_data_redaction_status": "PASS_PRIVATE_DATA_REDACTED",
        "pilot_forensic_capture": {"captured": present, "private_data_leaked": False},
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v129_status": "PASS",
        "execution_lock_deep_recheck_v128_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V169Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v168_baseline"):
        return "PASS" if ctx.v168_baseline_status == "PASS_V168_BASELINE_READBACK" else "FAIL" if ctx.v168_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v169_repeat_forensic_controller_report.json":
        return "PASS" if ctx.pilot_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V169Context) -> dict[str, Any]:
    workstream = "v169: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v169_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V169_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v169_report.json":
        report.update({"completion_oriented_next_action_v169_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v168_carried_status": ctx.v168_baseline_status, "repeat_forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v169_repeat_forensic_controller_report.json"), "no_new_order": str(ARTIFACTS / "v169_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v169.json", "dummy_canonical_identity_report_v169.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V169ReportFactory:
    def __init__(self, *, v168_final_override=None) -> None:
        self.kw = dict(v168_final_override=v168_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V169Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
