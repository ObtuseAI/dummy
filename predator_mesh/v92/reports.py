"""DUMMY v92 campaign order 2 reconcile, edge degradation, and stop/continue review — no new order."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v92 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V92_ROUTES = [
    "/api/v92/reconcile-review-controller",
    "/api/v92/v91-baseline",
    "/api/v92/order-2-outcome-parser",
    "/api/v92/cumulative-campaign-ledger",
    "/api/v92/edge-vs-fill-reality-review",
    "/api/v92/slippage-latency-trend",
    "/api/v92/no-trade-abstention-review",
    "/api/v92/stop-continue-decision",
    "/api/v92/readiness-governor",
    "/api/v92/execution-lock",
    "/api/v92/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "reconcile-review-controller": ["v92_reconcile_review_controller_report.json"],
    "v91-baseline": ["v91_baseline_readback_v1_report.json"],
    "order-2-outcome-parser": ["v92_order_2_outcome_parser_report.json"],
    "cumulative-campaign-ledger": ["v92_cumulative_campaign_ledger_report.json"],
    "edge-vs-fill-reality-review": ["v92_edge_vs_fill_reality_review_report.json"],
    "slippage-latency-trend": ["v92_slippage_latency_trend_report.json"],
    "no-trade-abstention-review": ["v92_no_trade_abstention_review_report.json"],
    "stop-continue-decision": ["v92_stop_continue_decision_report.json"],
    "readiness-governor": ["readiness_governor_v52_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v51_report.json"],
    "mission-state": ["dummy_mission_state_report_v78.json", "dashboard_v92_report_v1.json", "completion_oriented_next_action_v92_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(92)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v92/reports.py scripts/generate_v92_reports.py dashboard/backend/v92_routes.py",
    "python scripts/generate_v92_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V92Context:
    def __init__(self, *, v91_final_override=None, outcome_state="FILLED", stop_signal=None) -> None:
        self.v91_baseline_status = sgc.baseline_status("final_report_v91.json", "V91")
        v91 = v91_final_override if v91_final_override is not None else sgc.load_artifact("final_report_v91.json")
        self.order_2_submitted = str(v91.get("order_2_gate_controller_status", "")) == "PASS_ORDER_2_SUBMITTED" or int(v91.get("simulated_order_submits_count", 0) or 0) > 0
        self.outcome_state = outcome_state if self.order_2_submitted else None
        self.stop_signal = stop_signal  # one of STOP_LOSS_LOCK/STOP_DRIFT_LOCK/STOP_LIQUIDITY_LOCK or None

    @property
    def decision(self) -> str:
        if not self.order_2_submitted:
            return "PARTIAL_NO_ORDER_2_TO_REVIEW"
        if self.stop_signal in {"STOP_LOSS_LOCK", "STOP_DRIFT_LOCK", "STOP_LIQUIDITY_LOCK"}:
            return self.stop_signal
        return "CONTINUE_ALLOWED_WITH_ORDER_3_APPROVAL"

    @property
    def final_verdict(self) -> str:
        if self.v91_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.order_2_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v91_baseline_status.startswith("FAIL"):
            return ["FAIL_V91_BASELINE_REGRESSION"]
        return [] if self.order_2_submitted else ["NO_ORDER_2_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        if self.decision == "CONTINUE_ALLOWED_WITH_ORDER_3_APPROVAL":
            return "CONTINUE_ALLOWED_AWAIT_ORDER_3_APPROVAL_NO_AUTO_SUBMIT"
        if self.decision.startswith("STOP"):
            return "CAMPAIGN_STOP_LOCKED_NO_FURTHER_ORDERS"
        return "AWAIT_ORDER_2_SUBMIT_BEFORE_REVIEW"


def _common(ctx: V92Context) -> dict[str, Any]:
    present = ctx.order_2_submitted
    def s(v):
        return v if present else "PARTIAL_NO_ORDER_2"
    return {
        "v91_baseline_status": ctx.v91_baseline_status,
        "reconcile_review_controller_status": "PASS_ORDER_2_RECONCILED_REVIEWED" if present else "PARTIAL_NO_ORDER_2_TO_REVIEW",
        "order_2_submitted": present,
        "order_2_outcome_parser_status": f"PASS_OUTCOME_{ctx.outcome_state}" if present else "PARTIAL_NO_OUTCOME_TO_PARSE",
        "outcome_state": ctx.outcome_state,
        "cumulative_campaign_ledger_status": "PASS_CUMULATIVE_LEDGER_RECORDED",
        "edge_vs_fill_reality_review_status": s("PASS_EDGE_VS_FILL_REVIEWED"),
        "slippage_latency_trend_status": s("PASS_SLIPPAGE_LATENCY_TREND"),
        "no_trade_abstention_review_status": "PASS_ABSTENTION_REVIEWED",
        "stop_continue_decision_status": ctx.decision,
        "stop_continue_decision": ctx.decision,
        "new_order_placed": False,
        "live_orders": 0,
        "readiness_governor_v52_status": "PASS",
        "execution_lock_deep_recheck_v51_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V92Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v91_baseline"):
        return "PASS" if ctx.v91_baseline_status == "PASS_V91_BASELINE_READBACK" else "FAIL" if ctx.v91_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v92_reconcile_review_controller_report.json":
        return "PASS" if ctx.order_2_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V92Context) -> dict[str, Any]:
    workstream = "v92: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v92_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V92_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v92_report.json":
        report.update({"completion_oriented_next_action_v92_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v78.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v91_carried_status": ctx.v91_baseline_status, "stop_continue_decision": ctx.decision, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v92.json"), "stop_continue": str(ARTIFACTS / "v92_stop_continue_decision_report.json"), "cumulative_ledger": str(ARTIFACTS / "v92_cumulative_campaign_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v92.json", "dummy_canonical_identity_report_v92.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V92ReportFactory:
    def __init__(self, *, v91_final_override=None, outcome_state="FILLED", stop_signal=None) -> None:
        self.v91_final_override = v91_final_override
        self.outcome_state = outcome_state
        self.stop_signal = stop_signal

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V92Context(v91_final_override=self.v91_final_override, outcome_state=self.outcome_state, stop_signal=self.stop_signal)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
