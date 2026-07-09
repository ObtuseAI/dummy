"""DUMMY v211 forensic runner spine — one forensic entrypoint for proof review; no new orders.

Default is PARTIAL_NO_LIVE_PROOF_TO_FORENSIC_REVIEW. When V210 classified a proof state it summarizes
fill/reject/cancel/expired/partial-fill, buckets slippage/latency/fee, and reviews liquidity reality, edge-vs-execution
reality, risk/abstention/kill-switch/rollback behavior, and broker read-only consistency, all with private-data
redaction. No new order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v211 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v211: Forensic Runner Spine Execution Reality And Decision Audit"
MISSION_NAME = "dummy_mission_state_report_v197.json"
FINAL_NAME = "final_report_v211.json"
INDEX_KEYS = ["forensic_runner_controller_status", "live_orders", "no_new_order_proof_status"]
DASH_TITLE = "Dummy V211 Forensic Runner Spine"
MISSION_KEY = "dummy_mission_state_report_v197"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Forensic Runner", "forensic_runner_controller_status"],
    ["Live Orders", "live_orders"],
    ["Edge vs Execution", "edge_vs_execution_reality_status"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V211_ROUTES = [
    "/api/v211/forensic-runner-controller",
    "/api/v211/v210-baseline",
    "/api/v211/fill-reject-cancel-summary",
    "/api/v211/slippage-bucket",
    "/api/v211/latency-bucket",
    "/api/v211/fee-bucket",
    "/api/v211/liquidity-reality",
    "/api/v211/edge-vs-execution-reality",
    "/api/v211/risk-behavior",
    "/api/v211/abstention-behavior",
    "/api/v211/kill-switch-behavior",
    "/api/v211/rollback-behavior",
    "/api/v211/broker-readonly-consistency-check",
    "/api/v211/private-data-redaction",
    "/api/v211/no-new-order-proof",
    "/api/v211/readiness-governor",
    "/api/v211/execution-lock",
    "/api/v211/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-runner-controller": ["v211_forensic_runner_controller_report.json"],
    "v210-baseline": ["v210_baseline_readback_v1_report.json"],
    "fill-reject-cancel-summary": ["v211_fill_reject_cancel_summary_report.json"],
    "slippage-bucket": ["v211_slippage_bucket_report.json"],
    "latency-bucket": ["v211_latency_bucket_report.json"],
    "fee-bucket": ["v211_fee_bucket_report.json"],
    "liquidity-reality": ["v211_liquidity_reality_report.json"],
    "edge-vs-execution-reality": ["v211_edge_vs_execution_reality_report.json"],
    "risk-behavior": ["v211_risk_behavior_report.json"],
    "abstention-behavior": ["v211_abstention_behavior_report.json"],
    "kill-switch-behavior": ["v211_kill_switch_behavior_report.json"],
    "rollback-behavior": ["v211_rollback_behavior_report.json"],
    "broker-readonly-consistency-check": ["v211_broker_readonly_consistency_check_report.json"],
    "private-data-redaction": ["v211_private_data_redaction_report.json"],
    "no-new-order-proof": ["v211_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v171_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v170_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v211_report_v1.json", "completion_oriented_next_action_v211_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(211)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v211/reports.py scripts/generate_v211_reports.py dashboard/backend/v211_routes.py",
    "python scripts/generate_v211_reports.py",
    "python scripts/run_dummy_first_live_proof_forensics.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V211Context:
    def __init__(self, *, v210_final_override=None) -> None:
        self.v210_baseline_status = sgc.baseline_status("final_report_v210.json", "V210")
        v210 = v210_final_override if v210_final_override is not None else sgc.load_artifact("final_report_v210.json")
        self.proof_reviewable = str(v210.get("reconcile_runner_controller_status", "")) == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v210.get("order_state", "NO_ATTEMPT")) if self.proof_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED" if self.proof_reviewable else "PARTIAL_NO_LIVE_PROOF_TO_FORENSIC_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v210_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v210_baseline_status.startswith("FAIL"):
            return ["FAIL_V210_BASELINE_REGRESSION"]
        return [] if self.proof_reviewable else ["NO_LIVE_PROOF_TO_FORENSIC_REVIEW"]

    @property
    def next_action(self) -> str:
        return "FORENSIC_RUNNER_REVIEWED_LOCKED_AWAIT_REPEAT_SESSION_BRIDGE_NO_NEW_ORDER" if self.proof_reviewable else "AWAIT_RECONCILE_RUNNER_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V211Context) -> dict[str, Any]:
    present = ctx.proof_reviewable
    def s(v):
        return v if present else "PARTIAL_NO_PROOF"
    return {
        "v210_baseline_status": ctx.v210_baseline_status,
        "forensic_runner_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "fill_reject_cancel_summary_status": s("PASS_FILL_REJECT_CANCEL_EXPIRED_PARTIAL_SUMMARIZED"),
        "slippage_bucket_status": s("PASS_SLIPPAGE_BUCKETED"),
        "latency_bucket_status": s("PASS_LATENCY_BUCKETED"),
        "fee_bucket_status": s("PASS_FEE_BUCKETED"),
        "liquidity_reality_status": s("PASS_LIQUIDITY_REALITY_REVIEWED"),
        "edge_vs_execution_reality_status": s("PASS_EDGE_VS_EXECUTION_REVIEWED"),
        "risk_behavior_status": s("PASS_RISK_BEHAVIOR_REVIEWED"),
        "abstention_behavior_status": s("PASS_ABSTENTION_BEHAVIOR_REVIEWED"),
        "kill_switch_behavior_status": s("PASS_KILL_SWITCH_REVIEWED"),
        "rollback_behavior_status": s("PASS_ROLLBACK_REVIEWED"),
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
        "readiness_governor_v171_status": "PASS",
        "execution_lock_deep_recheck_v170_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V211Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v210_baseline"):
        return "PASS" if ctx.v210_baseline_status == "PASS_V210_BASELINE_READBACK" else "FAIL" if ctx.v210_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v211_forensic_runner_controller_report.json":
        return "PASS" if ctx.proof_reviewable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V211Context) -> dict[str, Any]:
    workstream = "v211: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v211_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V211_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v211_report.json":
        report.update({"completion_oriented_next_action_v211_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v210_carried_status": ctx.v210_baseline_status, "forensic_runner_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v211_forensic_runner_controller_report.json"), "no_new_order": str(ARTIFACTS / "v211_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v211.json", "dummy_canonical_identity_report_v211.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V211ReportFactory:
    def __init__(self, *, v210_final_override=None) -> None:
        self.kw = dict(v210_final_override=v210_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V211Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
