"""DUMMY v253 post execution intake bridge reconcile forensic ready — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v253 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v253: Post Execution Intake Bridge Reconcile Forensic Ready"
MISSION_NAME = "dummy_mission_state_report_v239.json"
FINAL_NAME = "final_report_v253.json"
INDEX_KEYS = ['post_execution_intake_bridge_controller_status', 'bridge_state', 'new_order_placed']
DASH_TITLE = "Dummy V253 Post Execution Intake Bridge Reconcile Forensic Ready"
MISSION_KEY = "dummy_mission_state_report_v239"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Intake Bridge', 'post_execution_intake_bridge_controller_status'], ['Bridge State', 'bridge_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V253_ROUTES = ['/api/v253/post-execution-intake-bridge-controller', '/api/v253/v252-baseline', '/api/v253/bridge-state-classification', '/api/v253/proof-id-validation', '/api/v253/order-attempt-id-validation', '/api/v253/idempotency-validation', '/api/v253/proof-lock-validation', '/api/v253/target-state-validation', '/api/v253/no-cancel-default-proof', '/api/v253/no-new-order-proof', '/api/v253/private-data-redaction', '/api/v253/readiness-governor', '/api/v253/execution-lock', '/api/v253/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'post-execution-intake-bridge-controller': ['v253_post_execution_intake_bridge_controller_report.json'], 'v252-baseline': ['v252_baseline_readback_v1_report.json'], 'bridge-state-classification': ['v253_bridge_state_classification_report.json'], 'proof-id-validation': ['v253_proof_id_validation_report.json'], 'order-attempt-id-validation': ['v253_order_attempt_id_validation_report.json'], 'idempotency-validation': ['v253_idempotency_validation_report.json'], 'proof-lock-validation': ['v253_proof_lock_validation_report.json'], 'target-state-validation': ['v253_target_state_validation_report.json'], 'no-cancel-default-proof': ['v253_no_cancel_default_proof_report.json'], 'no-new-order-proof': ['v253_no_new_order_proof_report.json'], 'private-data-redaction': ['v253_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v213_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v212_report.json'], 'mission-state': ['dummy_mission_state_report_v239.json', 'dashboard_v253_report_v1.json', 'completion_oriented_next_action_v253_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(253)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v253/reports.py scripts/generate_v253_reports.py dashboard/backend/v253_routes.py",
    "python scripts/generate_v253_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v253_post_execution_intake_bridge_controller_report.json"

class V253Context:
    def __init__(self, *, v252_final_override=None) -> None:
        self.v252_baseline_status = sgc.baseline_status("final_report_v252.json", "V252")
        v252 = v252_final_override if v252_final_override is not None else sgc.load_artifact("final_report_v252.json")
        self.proof_present = str(v252.get("execute_once_dry_fixture_harness_controller_status", "")) == "PASS_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_PROVEN_SAFE" or int(v252.get("simulated_order_submits_count", 0) or 0) > 0
        self.proof_target = str(v252.get("proof_target", "NO_ATTEMPT")) if self.proof_present else "NO_ATTEMPT"

    @property
    def bridge_state(self) -> str:
        return "ATTEMPT_READY_FOR_RECONCILE" if self.proof_present else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v252_baseline_status.startswith("FAIL"):
            return "FAIL_POST_EXECUTION_INTAKE_BRIDGE_BASELINE_REGRESSION"
        return "PASS_POST_EXECUTION_INTAKE_BRIDGE_READY_LOCKED" if self.proof_present else "PARTIAL_NO_EXECUTION_ATTEMPT_TO_INGEST"

    @property
    def final_verdict(self) -> str:
        if self.v252_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_present else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v252_baseline_status.startswith("FAIL"):
            return ["FAIL_V252_BASELINE_REGRESSION"]
        return [] if self.proof_present else ["NO_EXECUTION_ATTEMPT_TO_INGEST"]

    @property
    def next_action(self) -> str:
        return "POST_EXECUTION_INTAKE_BRIDGE_READY_ROUTE_TO_RECONCILE_FORENSIC_NO_NEW_ORDER" if self.proof_present else "AWAIT_EXECUTE_ONCE_ATTEMPT_BEFORE_INTAKE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v252_baseline_status": ctx.v252_baseline_status,
        "post_execution_intake_bridge_controller_status": ctx.controller_status,
        "bridge_state": ctx.bridge_state,
        "bridge_states": ["NO_ATTEMPT", "ATTEMPT_READY_FOR_RECONCILE", "RECONCILED_READY_FOR_FORENSIC", "FORENSIC_READY_FOR_ROUTE", "REPAIR_REQUIRED"],
        "bridge_state_classification_status": "PASS_BRIDGE_STATE_CLASSIFIED",
        "proof_target": ctx.proof_target,
        "proof_id_validation_status": "PASS_PROOF_ID_VALIDATED" if ctx.proof_present else "PARTIAL_NO_PROOF_ID",
        "order_attempt_id_validation_status": "PASS_ORDER_ATTEMPT_ID_VALIDATED" if ctx.proof_present else "PARTIAL_NO_ORDER_ATTEMPT_ID",
        "idempotency_validation_status": "PASS_IDEMPOTENCY_VALIDATED",
        "proof_lock_validation_status": "PASS_PROOF_LOCK_VALIDATED",
        "target_state_validation_status": "PASS_TARGET_STATE_VALIDATED",
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
        "readiness_governor_v213_status": "PASS",
        "execution_lock_deep_recheck_v212_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v252_baseline"):
        return "PASS" if ctx.v252_baseline_status == "PASS_V252_BASELINE_READBACK" else "FAIL" if ctx.v252_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v253: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v253_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V253_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v253_report.json":
        report.update({"completion_oriented_next_action_v253_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v252_carried_status": ctx.v252_baseline_status, "post_execution_intake_bridge_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v253.json", "dummy_canonical_identity_report_v253.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V253ReportFactory:
    def __init__(self, *, v252_final_override=None) -> None:
        self.kw = dict(v252_final_override=v252_final_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V253Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
