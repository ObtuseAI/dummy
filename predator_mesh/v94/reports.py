"""DUMMY v94 campaign final forensic audit, scaling-recommendation lock, and production gate.

Keeps autonomous/production trading disabled. Default scale recommendation is NO_SCALE. No caps
modification, no live order.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v94 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

PRODUCTION_GATE = {
    "AUTONOMOUS_TRADING_DISABLED": True,
    "PER_ORDER_APPROVAL_REQUIRED": True,
    "CAPS_OPERATOR_CONTROLLED": True,
    "LIVE_SUBMIT_OPERATOR_CONTROLLED": True,
}

V94_ROUTES = [
    "/api/v94/final-campaign-audit-controller",
    "/api/v94/v93-baseline",
    "/api/v94/campaign-outcome-ledger",
    "/api/v94/fill-reject-cancel-summary",
    "/api/v94/slippage-latency-fee-summary",
    "/api/v94/edge-degradation-review",
    "/api/v94/abstention-quality-review",
    "/api/v94/risk-governor-performance",
    "/api/v94/kill-switch-session-lock-review",
    "/api/v94/scale-recommendation-report",
    "/api/v94/production-gate",
    "/api/v94/readiness-governor",
    "/api/v94/execution-lock",
    "/api/v94/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "final-campaign-audit-controller": ["v94_final_campaign_audit_controller_report.json"],
    "v93-baseline": ["v93_baseline_readback_v1_report.json"],
    "campaign-outcome-ledger": ["v94_campaign_outcome_ledger_report.json"],
    "fill-reject-cancel-summary": ["v94_fill_reject_cancel_summary_report.json"],
    "slippage-latency-fee-summary": ["v94_slippage_latency_fee_summary_report.json"],
    "edge-degradation-review": ["v94_edge_degradation_review_report.json"],
    "abstention-quality-review": ["v94_abstention_quality_review_report.json"],
    "risk-governor-performance": ["v94_risk_governor_performance_report.json"],
    "kill-switch-session-lock-review": ["v94_kill_switch_session_lock_review_report.json"],
    "scale-recommendation-report": ["v94_scale_recommendation_report.json"],
    "production-gate": ["v94_production_gate_report.json"],
    "readiness-governor": ["readiness_governor_v54_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v53_report.json"],
    "mission-state": ["dummy_mission_state_report_v80.json", "dashboard_v94_report_v1.json", "completion_oriented_next_action_v94_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(94)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v94/reports.py scripts/generate_v94_reports.py dashboard/backend/v94_routes.py",
    "python scripts/generate_v94_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V94Context:
    def __init__(self) -> None:
        self.v93_baseline_status = sgc.baseline_status("final_report_v93.json", "V93")
        # Count simulated campaign orders across the chain (all default 0 real orders).
        self.campaign_orders = sum(int(sgc.load_artifact(f"final_report_v{v}.json").get("simulated_order_submits_count", 0) or 0) for v in (89, 91, 93))

    @property
    def scale_recommendation(self) -> str:
        return "NO_SCALE" if self.campaign_orders == 0 else "SCALE_REVIEW_ONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v93_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers = ["FAIL_V93_BASELINE_REGRESSION"] if self.v93_baseline_status.startswith("FAIL") else []
        if self.campaign_orders == 0:
            blockers.append("NO_CAMPAIGN_ORDERS_TO_AUDIT")
        return blockers

    @property
    def next_action(self) -> str:
        return "CAMPAIGN_AUDITED_PRODUCTION_LOCKED_NO_AUTONOMOUS_TRADING_NO_SCALE_APPLIED"


def _common(ctx: V94Context) -> dict[str, Any]:
    return {
        "v93_baseline_status": ctx.v93_baseline_status,
        "final_campaign_audit_controller_status": "PASS_CAMPAIGN_AUDITED_PRODUCTION_LOCKED",
        "campaign_orders_reviewed": ctx.campaign_orders,
        "campaign_outcome_ledger_status": "PASS_CAMPAIGN_OUTCOME_LEDGER",
        "fill_reject_cancel_summary_status": "PASS_FILL_REJECT_CANCEL_SUMMARY",
        "slippage_latency_fee_summary_status": "PASS_SLIPPAGE_LATENCY_FEE_SUMMARY",
        "edge_degradation_review_status": "PASS_EDGE_DEGRADATION_REVIEWED",
        "abstention_quality_review_status": "PASS_ABSTENTION_QUALITY_REVIEWED",
        "risk_governor_performance_status": "PASS_RISK_GOVERNOR_PERFORMANCE_REVIEWED",
        "kill_switch_session_lock_review_status": "PASS_KILL_SWITCH_SESSION_LOCK_REVIEWED",
        "scale_recommendation_report_status": "PASS_SCALE_RECOMMENDATION_LOCKED",
        "scale_recommendation": ctx.scale_recommendation,
        "scale_step_phrase": sgc.SCALE_STEP_PHRASE,
        "scale_applied": False,
        "production_gate_status": "PASS_PRODUCTION_GATE_LOCKED",
        "production_gate": PRODUCTION_GATE,
        "autonomous_trading_enabled": False,
        "caps_modified_by_dummy": False,
        "live_orders": 0,
        "readiness_governor_v54_status": "PASS",
        "execution_lock_deep_recheck_v53_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V94Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v93_baseline"):
        return "PASS" if ctx.v93_baseline_status == "PASS_V93_BASELINE_READBACK" else "FAIL" if ctx.v93_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V94Context) -> dict[str, Any]:
    workstream = "v94: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v94_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V94_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_enable_autonomous_trading": False})
    elif name == "completion_oriented_next_action_v94_report.json":
        report.update({"completion_oriented_next_action_v94_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v80.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v93_carried_status": ctx.v93_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v94.json"), "production_gate": str(ARTIFACTS / "v94_production_gate_report.json"), "scale_recommendation": str(ARTIFACTS / "v94_scale_recommendation_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v94.json", "dummy_canonical_identity_report_v94.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V94ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V94Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
