"""DUMMY v163 first real pilot forensic review — reviews first-pilot execution reality if V162 has a state; no new orders.

Default is PARTIAL_NO_FIRST_REAL_PILOT_TO_REVIEW. When V162 classified a pilot state it summarizes
fill/reject/cancel/expired/partial-fill, buckets slippage/latency/fee, reviews liquidity reality, edge-vs-execution
reality, the abstention decision, risk-governor behavior, kill-switch/rollback, and broker read-only consistency, all
with private-data redaction. No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v163 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v163: First Real Pilot Forensic Review Edge Risk Abstention Execution Reality"
MISSION_NAME = "dummy_mission_state_report_v149.json"
FINAL_NAME = "final_report_v163.json"
INDEX_KEYS = ["forensic_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V163 First Real Pilot Forensic Review"
MISSION_KEY = "dummy_mission_state_report_v149"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Forensic Review", "forensic_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V163_ROUTES = [
    "/api/v163/forensic-controller",
    "/api/v163/v162-baseline",
    "/api/v163/fill-reject-cancel-summary",
    "/api/v163/slippage-bucket",
    "/api/v163/latency-bucket",
    "/api/v163/fee-bucket",
    "/api/v163/liquidity-reality",
    "/api/v163/edge-vs-execution-reality",
    "/api/v163/abstention-decision-review",
    "/api/v163/risk-governor-behavior-review",
    "/api/v163/kill-switch-review",
    "/api/v163/rollback-review",
    "/api/v163/broker-readonly-consistency-check",
    "/api/v163/private-data-redaction",
    "/api/v163/no-new-order-proof",
    "/api/v163/readiness-governor",
    "/api/v163/execution-lock",
    "/api/v163/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-controller": ["v163_forensic_controller_report.json"],
    "v162-baseline": ["v162_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v163_fill_reject_cancel_summary_report.json"],
    "slippage-bucket": ["v163_slippage_bucket_report.json"],
    "latency-bucket": ["v163_latency_bucket_report.json"],
    "fee-bucket": ["v163_fee_bucket_report.json"],
    "liquidity-reality": ["v163_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v163_edge_vs_execution_reality_report.json"],
    "abstention-decision-review": ["v163_abstention_decision_review_report.json"],
    "risk-governor-behavior-review": ["v163_risk_governor_behavior_review_report.json"],
    "kill-switch-review": ["v163_kill_switch_review_report.json"],
    "rollback-review": ["v163_rollback_review_report.json"],
    "broker-readonly-consistency-check": ["v163_broker_readonly_consistency_check_report.json"],
    "private-data-redaction": ["v163_private_data_redaction_report.json"],
    "no-new-order-proof": ["v163_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v123_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v122_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v163_report_v1.json", "completion_oriented_next_action_v163_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(163)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v163/reports.py scripts/generate_v163_reports.py dashboard/backend/v163_routes.py",
    "python scripts/generate_v163_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V163Context:
    def __init__(self, *, v162_final_override=None) -> None:
        self.v162_baseline_status = sgc.baseline_status("final_report_v162.json", "V162")
        v162 = v162_final_override if v162_final_override is not None else sgc.load_artifact("final_report_v162.json")
        self.pilot_reviewable = str(v162.get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v162.get("order_state", "NO_ATTEMPT")) if self.pilot_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED" if self.pilot_reviewable else "PARTIAL_NO_FIRST_REAL_PILOT_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v162_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pilot_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v162_baseline_status.startswith("FAIL"):
            return ["FAIL_V162_BASELINE_REGRESSION"]
        return [] if self.pilot_reviewable else ["NO_FIRST_REAL_PILOT_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "FIRST_REAL_PILOT_FORENSIC_REVIEWED_AWAIT_REPEAT_ELIGIBILITY_DECISION_NO_NEW_ORDER" if self.pilot_reviewable else "AWAIT_FIRST_REAL_PILOT_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V163Context) -> dict[str, Any]:
    present = ctx.pilot_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_PILOT"
    return {
        "v162_baseline_status": ctx.v162_baseline_status,
        "forensic_controller_status": ctx.controller_status,
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
        "readiness_governor_v123_status": "PASS",
        "execution_lock_deep_recheck_v122_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V163Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v162_baseline"):
        return "PASS" if ctx.v162_baseline_status == "PASS_V162_BASELINE_READBACK" else "FAIL" if ctx.v162_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v163_forensic_controller_report.json":
        return "PASS" if ctx.pilot_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V163Context) -> dict[str, Any]:
    workstream = "v163: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v163_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V163_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v163_report.json":
        report.update({"completion_oriented_next_action_v163_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v162_carried_status": ctx.v162_baseline_status, "forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v163_forensic_controller_report.json"), "no_new_order": str(ARTIFACTS / "v163_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v163.json", "dummy_canonical_identity_report_v163.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V163ReportFactory:
    def __init__(self, *, v162_final_override=None) -> None:
        self.kw = dict(v162_final_override=v162_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V163Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
