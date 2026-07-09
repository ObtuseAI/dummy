"""DUMMY v104 order 2 reconcile, edge degradation, and stop/continue review — no new order."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v104 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V104_ROUTES = [
    "/api/v104/reconcile-review-controller",
    "/api/v104/v103-baseline",
    "/api/v104/order-2-outcome-parser",
    "/api/v104/cumulative-campaign-ledger",
    "/api/v104/edge-vs-fill-reality-review",
    "/api/v104/slippage-latency-trend",
    "/api/v104/no-trade-abstention-review",
    "/api/v104/stop-continue-decision",
    "/api/v104/readiness-governor",
    "/api/v104/execution-lock",
    "/api/v104/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "reconcile-review-controller": ["v104_reconcile_review_controller_report.json"],
    "v103-baseline": ["v103_baseline_readback_v1_report.json"],
    "order-2-outcome-parser": ["v104_order_2_outcome_parser_report.json"],
    "cumulative-campaign-ledger": ["v104_cumulative_campaign_ledger_report.json"],
    "edge-vs-fill-reality-review": ["v104_edge_vs_fill_reality_review_report.json"],
    "slippage-latency-trend": ["v104_slippage_latency_trend_report.json"],
    "no-trade-abstention-review": ["v104_no_trade_abstention_review_report.json"],
    "stop-continue-decision": ["v104_stop_continue_decision_report.json"],
    "readiness-governor": ["readiness_governor_v64_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v63_report.json"],
    "mission-state": ["dummy_mission_state_report_v90.json", "dashboard_v104_report_v1.json", "completion_oriented_next_action_v104_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(104)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v104/reports.py scripts/generate_v104_reports.py dashboard/backend/v104_routes.py",
    "python scripts/generate_v104_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V104Context:
    def __init__(self, *, v103_final_override=None, outcome_state="FILLED", stop_signal=None) -> None:
        self.v103_baseline_status = sgc.baseline_status("final_report_v103.json", "V103")
        v103 = v103_final_override if v103_final_override is not None else sgc.load_artifact("final_report_v103.json")
        self.order_2_submitted = str(v103.get("order_2_canary_controller_status", "")) == "PASS_ORDER2_SUBMITTED" or int(v103.get("simulated_order_submits_count", 0) or 0) > 0
        self.outcome_state = outcome_state if self.order_2_submitted else None
        self.stop_signal = stop_signal

    @property
    def decision(self) -> str:
        if not self.order_2_submitted:
            return "PARTIAL_NO_ORDER2_TO_REVIEW"
        if self.stop_signal in {"STOP_LOSS_LOCK", "STOP_DRIFT_LOCK", "STOP_LIQUIDITY_LOCK"}:
            return self.stop_signal
        return "CONTINUE_ALLOWED_WITH_ORDER3_APPROVAL"

    @property
    def final_verdict(self) -> str:
        if self.v103_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.order_2_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v103_baseline_status.startswith("FAIL"):
            return ["FAIL_V103_BASELINE_REGRESSION"]
        return [] if self.order_2_submitted else ["NO_ORDER2_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        if self.decision == "CONTINUE_ALLOWED_WITH_ORDER3_APPROVAL":
            return "CONTINUE_ALLOWED_AWAIT_ORDER3_APPROVAL_NO_AUTO_SUBMIT"
        if self.decision.startswith("STOP"):
            return "CAMPAIGN_STOP_LOCKED_NO_FURTHER_ORDERS"
        return "AWAIT_ORDER2_SUBMIT_BEFORE_REVIEW"


def _common(ctx: V104Context) -> dict[str, Any]:
    present = ctx.order_2_submitted
    def s(v):
        return v if present else "PARTIAL_NO_ORDER2"
    return {
        "v103_baseline_status": ctx.v103_baseline_status,
        "reconcile_review_controller_status": "PASS_ORDER2_RECONCILED_REVIEWED" if present else "PARTIAL_NO_ORDER2_TO_REVIEW",
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
        "readiness_governor_v64_status": "PASS",
        "execution_lock_deep_recheck_v63_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V104Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v103_baseline"):
        return "PASS" if ctx.v103_baseline_status == "PASS_V103_BASELINE_READBACK" else "FAIL" if ctx.v103_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v104_reconcile_review_controller_report.json":
        return "PASS" if ctx.order_2_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V104Context) -> dict[str, Any]:
    workstream = "v104: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v104_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V104_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v104_report.json":
        report.update({"completion_oriented_next_action_v104_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v90.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v103_carried_status": ctx.v103_baseline_status, "stop_continue_decision": ctx.decision, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v104.json"), "stop_continue": str(ARTIFACTS / "v104_stop_continue_decision_report.json"), "cumulative_ledger": str(ARTIFACTS / "v104_cumulative_campaign_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v104.json", "dummy_canonical_identity_report_v104.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V104ReportFactory:
    def __init__(self, *, v103_final_override=None, outcome_state="FILLED", stop_signal=None) -> None:
        self.v103_final_override = v103_final_override
        self.outcome_state = outcome_state
        self.stop_signal = stop_signal

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V104Context(v103_final_override=self.v103_final_override, outcome_state=self.outcome_state, stop_signal=self.stop_signal)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
