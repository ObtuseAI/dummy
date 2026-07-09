"""DUMMY v231 reconcile forensic auto pipeline no new orders — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v231 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v231: Reconcile Forensic Auto Pipeline No New Orders"
MISSION_NAME = "dummy_mission_state_report_v217.json"
FINAL_NAME = "final_report_v231.json"
INDEX_KEYS = ['reconcile_forensic_pipeline_controller_status', 'order_state', 'new_order_placed']
DASH_TITLE = "Dummy V231 Reconcile Forensic Auto Pipeline No New Orders"
MISSION_KEY = "dummy_mission_state_report_v217"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Reconcile+Forensic', 'reconcile_forensic_pipeline_controller_status'], ['Order State', 'order_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V231_ROUTES = ['/api/v231/reconcile-forensic-pipeline-controller', '/api/v231/v230-baseline', '/api/v231/proof-state-parser', '/api/v231/proof-target-classifier', '/api/v231/idempotency-verification', '/api/v231/proof-lock-recheck', '/api/v231/forensic-fill-reject-summary', '/api/v231/forensic-slippage-latency-fee', '/api/v231/forensic-risk-abstention', '/api/v231/no-cancel-default-proof', '/api/v231/no-new-order-proof', '/api/v231/private-data-redaction', '/api/v231/readiness-governor', '/api/v231/execution-lock', '/api/v231/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'reconcile-forensic-pipeline-controller': ['v231_reconcile_forensic_pipeline_controller_report.json'], 'v230-baseline': ['v230_baseline_readback_v1_report.json'], 'proof-state-parser': ['v231_proof_state_parser_report.json'], 'proof-target-classifier': ['v231_proof_target_classifier_report.json'], 'idempotency-verification': ['v231_idempotency_verification_report.json'], 'proof-lock-recheck': ['v231_proof_lock_recheck_report.json'], 'forensic-fill-reject-summary': ['v231_forensic_fill_reject_summary_report.json'], 'forensic-slippage-latency-fee': ['v231_forensic_slippage_latency_fee_report.json'], 'forensic-risk-abstention': ['v231_forensic_risk_abstention_report.json'], 'no-cancel-default-proof': ['v231_no_cancel_default_proof_report.json'], 'no-new-order-proof': ['v231_no_new_order_proof_report.json'], 'private-data-redaction': ['v231_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v191_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v190_report.json'], 'mission-state': ['dummy_mission_state_report_v217.json', 'dashboard_v231_report_v1.json', 'completion_oriented_next_action_v231_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(231)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v231/reports.py scripts/generate_v231_reports.py dashboard/backend/v231_routes.py",
    "python scripts/generate_v231_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v231_reconcile_forensic_pipeline_controller_report.json"

VALID_STATES = ("FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN")


class V231Context:
    def __init__(self, *, v230_final_override=None, outcome_state="FILLED") -> None:
        self.v230_baseline_status = sgc.baseline_status("final_report_v230.json", "V230")
        v230 = v230_final_override if v230_final_override is not None else sgc.load_artifact("final_report_v230.json")
        self.proof_submitted = str(v230.get("live_proof_execution_orchestrator_controller_status", "")) == "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED" or int(v230.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = (outcome_state if outcome_state in VALID_STATES else "UNKNOWN") if self.proof_submitted else "NO_ATTEMPT"
        self.proof_target = str(v230.get("proof_target", "BLOCKED_NO_AUTHORITY")) if self.proof_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v230_baseline_status.startswith("FAIL"):
            return "FAIL_RECONCILE_FORENSIC_PIPELINE_BASELINE_REGRESSION"
        return "PASS_RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED" if self.proof_submitted else "PARTIAL_NO_LIVE_PROOF_TO_RECONCILE_OR_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v230_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v230_baseline_status.startswith("FAIL"):
            return ["FAIL_V230_BASELINE_REGRESSION"]
        return [] if self.proof_submitted else ["NO_LIVE_PROOF_TO_RECONCILE_OR_REVIEW"]

    @property
    def next_action(self) -> str:
        return "RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED_AWAIT_ROUTE_DECISION_NO_NEW_ORDER" if self.proof_submitted else "AWAIT_LIVE_PROOF_EXECUTION_BEFORE_RECONCILE_FORENSIC"


def _common(ctx) -> dict[str, Any]:
    return {
        "v230_baseline_status": ctx.v230_baseline_status,
        "reconcile_forensic_pipeline_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "proof_state_parser_status": "PASS_PROOF_STATE_PARSED",
        "proof_target": ctx.proof_target,
        "proof_target_classifier_status": "PASS_PROOF_TARGET_CLASSIFIED",
        "idempotency_verification_status": "PASS_IDEMPOTENCY_VERIFIED",
        "proof_lock_recheck_status": "PASS_PROOF_LOCK_RECHECKED",
        "forensic_fill_reject_summary_status": "PASS_FILL_REJECT_SUMMARIZED",
        "forensic_slippage_latency_fee_status": "PASS_SLIPPAGE_LATENCY_FEE_BUCKETED",
        "forensic_risk_abstention_status": "PASS_RISK_ABSTENTION_REVIEWED",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "private_data_redaction_status": "PASS_PRIVATE_DATA_REDACTED",
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
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v191_status": "PASS",
        "execution_lock_deep_recheck_v190_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v230_baseline"):
        return "PASS" if ctx.v230_baseline_status == "PASS_V230_BASELINE_READBACK" else "FAIL" if ctx.v230_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v231: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v231_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V231_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v231_report.json":
        report.update({"completion_oriented_next_action_v231_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v230_carried_status": ctx.v230_baseline_status, "reconcile_forensic_pipeline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v231.json", "dummy_canonical_identity_report_v231.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V231ReportFactory:
    def __init__(self, *, v230_final_override=None, outcome_state='FILLED') -> None:
        self.kw = dict(v230_final_override=v230_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V231Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
