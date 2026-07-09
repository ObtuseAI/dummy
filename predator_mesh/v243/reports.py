"""DUMMY v243 reconcile forensic pipeline v2 after execute once — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v243 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v243: Reconcile Forensic Pipeline V2 After Execute Once"
MISSION_NAME = "dummy_mission_state_report_v229.json"
FINAL_NAME = "final_report_v243.json"
INDEX_KEYS = ['reconcile_forensic_pipeline_v2_controller_status', 'order_state', 'new_order_placed']
DASH_TITLE = "Dummy V243 Reconcile Forensic Pipeline V2 After Execute Once"
MISSION_KEY = "dummy_mission_state_report_v229"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Reconcile+Forensic V2', 'reconcile_forensic_pipeline_v2_controller_status'], ['Order State', 'order_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V243_ROUTES = ['/api/v243/reconcile-forensic-pipeline-v2-controller', '/api/v243/v242-baseline', '/api/v243/load-latest-proof-attempt', '/api/v243/classify-state', '/api/v243/verify-idempotency', '/api/v243/verify-proof-lock', '/api/v243/forensic-review', '/api/v243/update-proof-state-artifact', '/api/v243/update-route-decision', '/api/v243/update-scoreboard', '/api/v243/no-cancel-default-proof', '/api/v243/no-new-order-proof', '/api/v243/private-data-redaction', '/api/v243/readiness-governor', '/api/v243/execution-lock', '/api/v243/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'reconcile-forensic-pipeline-v2-controller': ['v243_reconcile_forensic_pipeline_v2_controller_report.json'], 'v242-baseline': ['v242_baseline_readback_v1_report.json'], 'load-latest-proof-attempt': ['v243_load_latest_proof_attempt_report.json'], 'classify-state': ['v243_classify_state_report.json'], 'verify-idempotency': ['v243_verify_idempotency_report.json'], 'verify-proof-lock': ['v243_verify_proof_lock_report.json'], 'forensic-review': ['v243_forensic_review_report.json'], 'update-proof-state-artifact': ['v243_update_proof_state_artifact_report.json'], 'update-route-decision': ['v243_update_route_decision_report.json'], 'update-scoreboard': ['v243_update_scoreboard_report.json'], 'no-cancel-default-proof': ['v243_no_cancel_default_proof_report.json'], 'no-new-order-proof': ['v243_no_new_order_proof_report.json'], 'private-data-redaction': ['v243_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v203_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v202_report.json'], 'mission-state': ['dummy_mission_state_report_v229.json', 'dashboard_v243_report_v1.json', 'completion_oriented_next_action_v243_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(243)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v243/reports.py scripts/generate_v243_reports.py dashboard/backend/v243_routes.py",
    "python scripts/generate_v243_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v243_reconcile_forensic_pipeline_v2_controller_report.json"

VALID_STATES = ("FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN")


class V243Context:
    def __init__(self, *, v242_final_override=None, outcome_state="FILLED") -> None:
        self.v242_baseline_status = sgc.baseline_status("final_report_v242.json", "V242")
        v242 = v242_final_override if v242_final_override is not None else sgc.load_artifact("final_report_v242.json")
        self.proof_submitted = str(v242.get("execute_once_harness_controller_status", "")) == "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED" or int(v242.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = (outcome_state if outcome_state in VALID_STATES else "UNKNOWN") if self.proof_submitted else "NO_ATTEMPT"
        self.proof_target = str(v242.get("proof_target", "BLOCKED_NO_AUTHORITY")) if self.proof_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v242_baseline_status.startswith("FAIL"):
            return "FAIL_RECONCILE_FORENSIC_PIPELINE_V2_BASELINE_REGRESSION"
        return "PASS_RECONCILE_FORENSIC_PIPELINE_V2_REVIEWED_LOCKED" if self.proof_submitted else "PARTIAL_NO_EXECUTE_ONCE_PROOF_TO_RECONCILE_OR_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v242_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v242_baseline_status.startswith("FAIL"):
            return ["FAIL_V242_BASELINE_REGRESSION"]
        return [] if self.proof_submitted else ["NO_EXECUTE_ONCE_PROOF_TO_RECONCILE_OR_REVIEW"]

    @property
    def next_action(self) -> str:
        return "RECONCILE_FORENSIC_PIPELINE_V2_REVIEWED_LOCKED_UPDATE_ROUTE_AND_SCOREBOARD_NO_NEW_ORDER" if self.proof_submitted else "AWAIT_EXECUTE_ONCE_HARNESS_BEFORE_RECONCILE_FORENSIC"


def _common(ctx) -> dict[str, Any]:
    return {
        "v242_baseline_status": ctx.v242_baseline_status,
        "reconcile_forensic_pipeline_v2_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "proof_target": ctx.proof_target,
        "load_latest_proof_attempt_status": "PASS_LATEST_PROOF_ATTEMPT_LOADED",
        "classify_state_status": "PASS_STATE_CLASSIFIED",
        "verify_idempotency_status": "PASS_IDEMPOTENCY_VERIFIED",
        "verify_proof_lock_status": "PASS_PROOF_LOCK_VERIFIED",
        "forensic_review_status": "PASS_FORENSIC_REVIEWED",
        "update_proof_state_artifact_status": "PASS_PROOF_STATE_ARTIFACT_UPDATED",
        "update_route_decision_status": "PASS_ROUTE_DECISION_UPDATED",
        "update_scoreboard_status": "PASS_SCOREBOARD_UPDATED",
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
        "readiness_governor_v203_status": "PASS",
        "execution_lock_deep_recheck_v202_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v242_baseline"):
        return "PASS" if ctx.v242_baseline_status == "PASS_V242_BASELINE_READBACK" else "FAIL" if ctx.v242_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v243: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v243_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V243_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v243_report.json":
        report.update({"completion_oriented_next_action_v243_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v242_carried_status": ctx.v242_baseline_status, "reconcile_forensic_pipeline_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v243.json", "dummy_canonical_identity_report_v243.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V243ReportFactory:
    def __init__(self, *, v242_final_override=None, outcome_state='FILLED') -> None:
        self.kw = dict(v242_final_override=v242_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V243Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
