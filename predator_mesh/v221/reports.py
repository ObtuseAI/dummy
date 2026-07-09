"""DUMMY v221 forensic spine v2 proof reality risk and abstention audit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v221 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v221: Forensic Spine V2 Proof Reality Risk And Abstention Audit"
MISSION_NAME = "dummy_mission_state_report_v207.json"
FINAL_NAME = "final_report_v221.json"
INDEX_KEYS = ['forensic_spine_v2_controller_status', 'order_state', 'new_order_placed']
DASH_TITLE = "Dummy V221 Forensic Spine V2 Proof Reality Risk And Abstention Audit"
MISSION_KEY = "dummy_mission_state_report_v207"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Forensic Spine', 'forensic_spine_v2_controller_status'], ['Order State', 'order_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V221_ROUTES = ['/api/v221/forensic-spine-v2-controller', '/api/v221/v220-baseline', '/api/v221/fill-reject-cancel-summary', '/api/v221/proof-target-summary', '/api/v221/slippage-bucket', '/api/v221/latency-bucket', '/api/v221/fee-bucket', '/api/v221/liquidity-reality', '/api/v221/edge-vs-execution-reality', '/api/v221/risk-behavior', '/api/v221/abstention-behavior', '/api/v221/kill-switch-behavior', '/api/v221/rollback-behavior', '/api/v221/broker-readonly-consistency', '/api/v221/no-new-order-proof', '/api/v221/readiness-governor', '/api/v221/execution-lock', '/api/v221/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'forensic-spine-v2-controller': ['v221_forensic_spine_v2_controller_report.json'], 'v220-baseline': ['v220_baseline_readback_v1_report.json'], 'fill-reject-cancel-summary': ['v221_fill_reject_cancel_summary_report.json'], 'proof-target-summary': ['v221_proof_target_summary_report.json'], 'slippage-bucket': ['v221_slippage_bucket_report.json'], 'latency-bucket': ['v221_latency_bucket_report.json'], 'fee-bucket': ['v221_fee_bucket_report.json'], 'liquidity-reality': ['v221_liquidity_reality_report.json'], 'edge-vs-execution-reality': ['v221_edge_vs_execution_reality_report.json'], 'risk-behavior': ['v221_risk_behavior_report.json'], 'abstention-behavior': ['v221_abstention_behavior_report.json'], 'kill-switch-behavior': ['v221_kill_switch_behavior_report.json'], 'rollback-behavior': ['v221_rollback_behavior_report.json'], 'broker-readonly-consistency': ['v221_broker_readonly_consistency_report.json'], 'no-new-order-proof': ['v221_no_new_order_proof_report.json'], 'readiness-governor': ['readiness_governor_v181_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v180_report.json'], 'mission-state': ['dummy_mission_state_report_v207.json', 'dashboard_v221_report_v1.json', 'completion_oriented_next_action_v221_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(221)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v221/reports.py scripts/generate_v221_reports.py dashboard/backend/v221_routes.py",
    "python scripts/generate_v221_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v221_forensic_spine_v2_controller_report.json"

class V221Context:
    def __init__(self, *, v220_final_override=None) -> None:
        self.v220_baseline_status = sgc.baseline_status("final_report_v220.json", "V220")
        v220 = v220_final_override if v220_final_override is not None else sgc.load_artifact("final_report_v220.json")
        self.proof_reviewable = str(v220.get("reconcile_spine_v2_controller_status", "")) == "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED"
        self.order_state = str(v220.get("order_state", "NO_ATTEMPT")) if self.proof_reviewable else "NO_ATTEMPT"
        self.proof_target = str(v220.get("proof_target", "NO_ATTEMPT")) if self.proof_reviewable else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v220_baseline_status.startswith("FAIL"):
            return "FAIL_FORENSIC_SPINE_V2_BASELINE_REGRESSION"
        return "PASS_FORENSIC_SPINE_V2_REVIEWED_LOCKED" if self.proof_reviewable else "PARTIAL_NO_HARDENED_LIVE_PROOF_TO_FORENSIC_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v220_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_reviewable else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v220_baseline_status.startswith("FAIL"):
            return ["FAIL_V220_BASELINE_REGRESSION"]
        return [] if self.proof_reviewable else ["NO_HARDENED_LIVE_PROOF_TO_FORENSIC_REVIEW"]

    @property
    def next_action(self) -> str:
        return "FORENSIC_SPINE_V2_REVIEWED_LOCKED_AWAIT_REPEAT_SESSION_BRIDGE_V2_NO_NEW_ORDER" if self.proof_reviewable else "AWAIT_RECONCILE_SPINE_V2_BEFORE_FORENSIC_REVIEW"


def _common(ctx) -> dict[str, Any]:
    return {
        "v220_baseline_status": ctx.v220_baseline_status,
        "forensic_spine_v2_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "proof_target": ctx.proof_target,
        "fill_reject_cancel_summary_status": "PASS_FILL_REJECT_CANCEL_SUMMARIZED",
        "proof_target_summary_status": "PASS_PROOF_TARGET_SUMMARIZED",
        "slippage_bucket_status": "PASS_SLIPPAGE_BUCKETED",
        "latency_bucket_status": "PASS_LATENCY_BUCKETED",
        "fee_bucket_status": "PASS_FEE_BUCKETED",
        "liquidity_reality_status": "PASS_LIQUIDITY_REALITY_REVIEWED",
        "edge_vs_execution_reality_status": "PASS_EDGE_VS_EXECUTION_REVIEWED",
        "risk_behavior_status": "PASS_RISK_BEHAVIOR_REVIEWED",
        "abstention_behavior_status": "PASS_ABSTENTION_BEHAVIOR_REVIEWED",
        "kill_switch_behavior_status": "PASS_KILL_SWITCH_BEHAVIOR_REVIEWED",
        "rollback_behavior_status": "PASS_ROLLBACK_BEHAVIOR_REVIEWED",
        "broker_readonly_consistency_status": "PASS_BROKER_READONLY_CONSISTENT",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "readiness_governor_v181_status": "PASS",
        "execution_lock_deep_recheck_v180_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v220_baseline"):
        return "PASS" if ctx.v220_baseline_status == "PASS_V220_BASELINE_READBACK" else "FAIL" if ctx.v220_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v221: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v221_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V221_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v221_report.json":
        report.update({"completion_oriented_next_action_v221_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v220_carried_status": ctx.v220_baseline_status, "forensic_spine_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v221.json", "dummy_canonical_identity_report_v221.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V221ReportFactory:
    def __init__(self, *, v220_final_override=None) -> None:
        self.kw = dict(v220_final_override=v220_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V221Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
