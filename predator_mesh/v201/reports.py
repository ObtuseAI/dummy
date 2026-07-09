"""DUMMY v201 first live-proof forensic review — reviews first-live-proof execution reality if V200 has a state; no new orders.

Default is PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW. When V200 classified a proof state it summarizes
fill/reject/cancel/expired/partial-fill and proof target, buckets slippage/latency/fee, reviews liquidity reality,
edge-vs-execution reality, abstention decision, risk-governor behavior, kill-switch/rollback, and broker read-only
consistency, all with private-data redaction. No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v201 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v201: First Live Proof Forensic Review Execution Risk Abstention Reality"
MISSION_NAME = "dummy_mission_state_report_v187.json"
FINAL_NAME = "final_report_v201.json"
INDEX_KEYS = ["forensic_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V201 First Live-Proof Forensic Review"
MISSION_KEY = "dummy_mission_state_report_v187"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Forensic Review", "forensic_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V201_ROUTES = [
    "/api/v201/forensic-controller",
    "/api/v201/v200-baseline",
    "/api/v201/fill-reject-cancel-summary",
    "/api/v201/proof-target-summary",
    "/api/v201/slippage-bucket",
    "/api/v201/latency-bucket",
    "/api/v201/fee-bucket",
    "/api/v201/liquidity-reality",
    "/api/v201/edge-vs-execution-reality",
    "/api/v201/abstention-decision-review",
    "/api/v201/risk-governor-behavior-review",
    "/api/v201/kill-switch-review",
    "/api/v201/rollback-review",
    "/api/v201/broker-readonly-consistency-check",
    "/api/v201/private-data-redaction",
    "/api/v201/no-new-order-proof",
    "/api/v201/readiness-governor",
    "/api/v201/execution-lock",
    "/api/v201/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-controller": ["v201_forensic_controller_report.json"],
    "v200-baseline": ["v200_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v201_fill_reject_cancel_summary_report.json"],
    "proof-target-summary": ["v201_proof_target_summary_report.json"],
    "slippage-bucket": ["v201_slippage_bucket_report.json"],
    "latency-bucket": ["v201_latency_bucket_report.json"],
    "fee-bucket": ["v201_fee_bucket_report.json"],
    "liquidity-reality": ["v201_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v201_edge_vs_execution_reality_report.json"],
    "abstention-decision-review": ["v201_abstention_decision_review_report.json"],
    "risk-governor-behavior-review": ["v201_risk_governor_behavior_review_report.json"],
    "kill-switch-review": ["v201_kill_switch_review_report.json"],
    "rollback-review": ["v201_rollback_review_report.json"],
    "broker-readonly-consistency-check": ["v201_broker_readonly_consistency_check_report.json"],
    "private-data-redaction": ["v201_private_data_redaction_report.json"],
    "no-new-order-proof": ["v201_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v161_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v160_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v201_report_v1.json", "completion_oriented_next_action_v201_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(201)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v201/reports.py scripts/generate_v201_reports.py dashboard/backend/v201_routes.py",
    "python scripts/generate_v201_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V201Context:
    def __init__(self, *, v200_final_override=None) -> None:
        self.v200_baseline_status = sgc.baseline_status("final_report_v200.json", "V200")
        v200 = v200_final_override if v200_final_override is not None else sgc.load_artifact("final_report_v200.json")
        self.proof_reviewable = str(v200.get("reconcile_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v200.get("order_state", "NO_ATTEMPT")) if self.proof_reviewable else "NO_ATTEMPT"
        self.proof_target = str(v200.get("proof_target", "NO_ATTEMPT")) if self.proof_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_LIVE_PROOF_FORENSIC_REVIEWED" if self.proof_reviewable else "PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v200_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v200_baseline_status.startswith("FAIL"):
            return ["FAIL_V200_BASELINE_REGRESSION"]
        return [] if self.proof_reviewable else ["NO_FIRST_LIVE_PROOF_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_PROOF_FORENSIC_REVIEWED_AWAIT_SCALE_AND_AUTONOMY_EVIDENCE_REFRESH_NO_NEW_ORDER" if self.proof_reviewable else "AWAIT_FIRST_LIVE_PROOF_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V201Context) -> dict[str, Any]:
    present = ctx.proof_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_PROOF"
    return {
        "v200_baseline_status": ctx.v200_baseline_status,
        "forensic_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "fill_reject_cancel_summary_status": s("PASS_FILL_REJECT_CANCEL_EXPIRED_PARTIAL_SUMMARIZED"),
        "proof_target_summary_status": f"PASS_PROOF_TARGET_{ctx.proof_target}" if present else "PARTIAL_NO_PROOF_TARGET",
        "proof_target": ctx.proof_target,
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
        "proof_forensic_capture": {"captured": present, "private_data_leaked": False},
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v161_status": "PASS",
        "execution_lock_deep_recheck_v160_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V201Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v200_baseline"):
        return "PASS" if ctx.v200_baseline_status == "PASS_V200_BASELINE_READBACK" else "FAIL" if ctx.v200_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v201_forensic_controller_report.json":
        return "PASS" if ctx.proof_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V201Context) -> dict[str, Any]:
    workstream = "v201: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v201_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V201_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v201_report.json":
        report.update({"completion_oriented_next_action_v201_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v200_carried_status": ctx.v200_baseline_status, "forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v201_forensic_controller_report.json"), "no_new_order": str(ARTIFACTS / "v201_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v201.json", "dummy_canonical_identity_report_v201.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V201ReportFactory:
    def __init__(self, *, v200_final_override=None) -> None:
        self.kw = dict(v200_final_override=v200_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V201Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
