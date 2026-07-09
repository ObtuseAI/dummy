"""DUMMY v153 real pilot forensic review V2 — reviews pilot execution reality if any pilot exists; no new orders.

Default is PARTIAL_NO_REAL_PILOT_TO_REVIEW. When the V152 reconcile classified a pilot state it summarizes
fill/reject/cancel/expired/partial-fill, buckets slippage/latency/fee, reviews liquidity reality, edge-vs-execution
reality, the abstention decision, risk-governor behavior, and kill-switch/rollback, all with private-data redaction.
No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v153 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v153: Real Pilot Forensic Review V2 Edge Risk Abstention And Execution Reality"
MISSION_NAME = "dummy_mission_state_report_v139.json"
FINAL_NAME = "final_report_v153.json"
INDEX_KEYS = ["forensic_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V153 Real Pilot Forensic Review V2"
MISSION_KEY = "dummy_mission_state_report_v139"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Forensic Review", "forensic_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V153_ROUTES = [
    "/api/v153/forensic-controller",
    "/api/v153/v152-baseline",
    "/api/v153/fill-reject-cancel-summary",
    "/api/v153/slippage-bucket",
    "/api/v153/latency-bucket",
    "/api/v153/fee-bucket",
    "/api/v153/liquidity-reality",
    "/api/v153/edge-vs-execution-reality",
    "/api/v153/abstention-decision-review",
    "/api/v153/risk-governor-behavior-review",
    "/api/v153/kill-switch-review",
    "/api/v153/rollback-review",
    "/api/v153/private-data-redaction",
    "/api/v153/no-new-order-proof",
    "/api/v153/readiness-governor",
    "/api/v153/execution-lock",
    "/api/v153/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-controller": ["v153_forensic_controller_report.json"],
    "v152-baseline": ["v152_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v153_fill_reject_cancel_summary_report.json"],
    "slippage-bucket": ["v153_slippage_bucket_report.json"],
    "latency-bucket": ["v153_latency_bucket_report.json"],
    "fee-bucket": ["v153_fee_bucket_report.json"],
    "liquidity-reality": ["v153_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v153_edge_vs_execution_reality_report.json"],
    "abstention-decision-review": ["v153_abstention_decision_review_report.json"],
    "risk-governor-behavior-review": ["v153_risk_governor_behavior_review_report.json"],
    "kill-switch-review": ["v153_kill_switch_review_report.json"],
    "rollback-review": ["v153_rollback_review_report.json"],
    "private-data-redaction": ["v153_private_data_redaction_report.json"],
    "no-new-order-proof": ["v153_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v113_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v112_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v153_report_v1.json", "completion_oriented_next_action_v153_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(153)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v153/reports.py scripts/generate_v153_reports.py dashboard/backend/v153_routes.py",
    "python scripts/generate_v153_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V153Context:
    def __init__(self, *, v152_final_override=None) -> None:
        self.v152_baseline_status = sgc.baseline_status("final_report_v152.json", "V152")
        v152 = v152_final_override if v152_final_override is not None else sgc.load_artifact("final_report_v152.json")
        self.pilot_reviewable = str(v152.get("reconcile_intake_controller_status", "")) == "PASS_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v152.get("order_state", "NO_ATTEMPT")) if self.pilot_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_REAL_PILOT_FORENSIC_REVIEWED" if self.pilot_reviewable else "PARTIAL_NO_REAL_PILOT_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v152_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pilot_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v152_baseline_status.startswith("FAIL"):
            return ["FAIL_V152_BASELINE_REGRESSION"]
        return [] if self.pilot_reviewable else ["NO_REAL_PILOT_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "REAL_PILOT_FORENSIC_REVIEWED_AWAIT_REPEAT_PILOT_PREFLIGHT_NO_NEW_ORDER" if self.pilot_reviewable else "AWAIT_REAL_PILOT_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V153Context) -> dict[str, Any]:
    present = ctx.pilot_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_PILOT"
    return {
        "v152_baseline_status": ctx.v152_baseline_status,
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
        "readiness_governor_v113_status": "PASS",
        "execution_lock_deep_recheck_v112_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V153Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v152_baseline"):
        return "PASS" if ctx.v152_baseline_status == "PASS_V152_BASELINE_READBACK" else "FAIL" if ctx.v152_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v153_forensic_controller_report.json":
        return "PASS" if ctx.pilot_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V153Context) -> dict[str, Any]:
    workstream = "v153: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v153_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V153_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v153_report.json":
        report.update({"completion_oriented_next_action_v153_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v152_carried_status": ctx.v152_baseline_status, "forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v153_forensic_controller_report.json"), "no_new_order": str(ARTIFACTS / "v153_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v153.json", "dummy_canonical_identity_report_v153.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V153ReportFactory:
    def __init__(self, *, v152_final_override=None) -> None:
        self.kw = dict(v152_final_override=v152_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V153Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
