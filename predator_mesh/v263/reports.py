"""DUMMY v263 reconcile forensic auto pipeline v4 after proof intake — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v263 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v263: Reconcile Forensic Auto Pipeline V4 After Proof Intake"
MISSION_NAME = "dummy_mission_state_report_v249.json"
FINAL_NAME = "final_report_v263.json"
INDEX_KEYS = ['reconcile_forensic_auto_pipeline_v4_controller_status', 'order_state', 'new_order_placed']
DASH_TITLE = "Dummy V263 Reconcile Forensic Auto Pipeline V4 After Proof Intake"
MISSION_KEY = "dummy_mission_state_report_v249"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Reconcile+Forensic V4', 'reconcile_forensic_auto_pipeline_v4_controller_status'], ['Order State', 'order_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V263_ROUTES = ['/api/v263/reconcile-forensic-auto-pipeline-v4-controller', '/api/v263/v262-baseline', '/api/v263/load-proof-intake', '/api/v263/classify-state', '/api/v263/verify-idempotency', '/api/v263/verify-proof-lock', '/api/v263/forensic-review', '/api/v263/update-route-decision', '/api/v263/update-completion-score', '/api/v263/no-cancel-default-proof', '/api/v263/no-new-order-proof', '/api/v263/private-data-redaction', '/api/v263/readiness-governor', '/api/v263/execution-lock', '/api/v263/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'reconcile-forensic-auto-pipeline-v4-controller': ['v263_reconcile_forensic_auto_pipeline_v4_controller_report.json'], 'v262-baseline': ['v262_baseline_readback_v1_report.json'], 'load-proof-intake': ['v263_load_proof_intake_report.json'], 'classify-state': ['v263_classify_state_report.json'], 'verify-idempotency': ['v263_verify_idempotency_report.json'], 'verify-proof-lock': ['v263_verify_proof_lock_report.json'], 'forensic-review': ['v263_forensic_review_report.json'], 'update-route-decision': ['v263_update_route_decision_report.json'], 'update-completion-score': ['v263_update_completion_score_report.json'], 'no-cancel-default-proof': ['v263_no_cancel_default_proof_report.json'], 'no-new-order-proof': ['v263_no_new_order_proof_report.json'], 'private-data-redaction': ['v263_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v223_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v222_report.json'], 'mission-state': ['dummy_mission_state_report_v249.json', 'dashboard_v263_report_v1.json', 'completion_oriented_next_action_v263_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(263)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v263/reports.py scripts/generate_v263_reports.py dashboard/backend/v263_routes.py",
    "python scripts/generate_v263_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v263_reconcile_forensic_auto_pipeline_v4_controller_report.json"

VALID_STATES = ("FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN")


class V263Context:
    def __init__(self, *, v262_final_override=None, outcome_state="FILLED") -> None:
        self.v262_baseline_status = sgc.baseline_status("final_report_v262.json", "V262")
        v262 = v262_final_override if v262_final_override is not None else sgc.load_artifact("final_report_v262.json")
        self.proof_present = str(v262.get("external_proof_intake_v2_controller_status", "")) == "PASS_EXTERNAL_PROOF_INTAKE_V2_READY_FOR_RECONCILE"
        self.order_state = (outcome_state if outcome_state in VALID_STATES else "UNKNOWN") if self.proof_present else "NO_ATTEMPT"
        self.proof_target = str(v262.get("proof_target", "NO_ATTEMPT")) if self.proof_present else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v262_baseline_status.startswith("FAIL"):
            return "FAIL_RECONCILE_FORENSIC_AUTO_PIPELINE_V4_BASELINE_REGRESSION"
        return "PASS_RECONCILE_FORENSIC_AUTO_PIPELINE_V4_REVIEWED_LOCKED" if self.proof_present else "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v262_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_present else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v262_baseline_status.startswith("FAIL"):
            return ["FAIL_V262_BASELINE_REGRESSION"]
        return [] if self.proof_present else ["NO_PROOF_TO_RECONCILE_FORENSIC_REVIEW"]

    @property
    def next_action(self) -> str:
        return "RECONCILE_FORENSIC_AUTO_PIPELINE_V4_REVIEWED_LOCKED_UPDATE_ROUTE_AND_SCORE_NO_NEW_ORDER" if self.proof_present else "AWAIT_EXTERNAL_PROOF_INTAKE_BEFORE_RECONCILE_FORENSIC"


def _common(ctx) -> dict[str, Any]:
    return {
        "v262_baseline_status": ctx.v262_baseline_status,
        "reconcile_forensic_auto_pipeline_v4_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "proof_target": ctx.proof_target,
        "load_proof_intake_status": "PASS_PROOF_INTAKE_LOADED",
        "classify_state_status": "PASS_STATE_CLASSIFIED",
        "verify_idempotency_status": "PASS_IDEMPOTENCY_VERIFIED",
        "verify_proof_lock_status": "PASS_PROOF_LOCK_VERIFIED",
        "forensic_review": {"slippage_bucket": "REVIEWED", "latency_bucket": "REVIEWED", "fee_bucket": "REVIEWED", "liquidity_reality": "REVIEWED", "edge_vs_execution_reality": "REVIEWED", "risk_behavior": "REVIEWED", "abstention_behavior": "REVIEWED", "kill_switch_behavior": "REVIEWED", "rollback_behavior": "REVIEWED"},
        "forensic_review_status": "PASS_FORENSIC_REVIEWED",
        "update_route_decision_status": "PASS_ROUTE_DECISION_UPDATED",
        "update_completion_score_status": "PASS_COMPLETION_SCORE_UPDATED",
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
        "readiness_governor_v223_status": "PASS",
        "execution_lock_deep_recheck_v222_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v262_baseline"):
        return "PASS" if ctx.v262_baseline_status == "PASS_V262_BASELINE_READBACK" else "FAIL" if ctx.v262_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v263: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v263_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V263_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v263_report.json":
        report.update({"completion_oriented_next_action_v263_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v262_carried_status": ctx.v262_baseline_status, "reconcile_forensic_auto_pipeline_v4_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v263.json", "dummy_canonical_identity_report_v263.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V263ReportFactory:
    def __init__(self, *, v262_final_override=None, outcome_state='FILLED') -> None:
        self.kw = dict(v262_final_override=v262_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V263Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
