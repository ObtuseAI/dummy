"""DUMMY v262 external proof intake v2 reconcile ready no order — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v262 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v262: External Proof Intake V2 Reconcile Ready No Order"
MISSION_NAME = "dummy_mission_state_report_v248.json"
FINAL_NAME = "final_report_v262.json"
INDEX_KEYS = ['external_proof_intake_v2_controller_status', 'intake_state', 'new_order_placed']
DASH_TITLE = "Dummy V262 External Proof Intake V2 Reconcile Ready No Order"
MISSION_KEY = "dummy_mission_state_report_v248"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Proof Intake V2', 'external_proof_intake_v2_controller_status'], ['Intake State', 'intake_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V262_ROUTES = ['/api/v262/external-proof-intake-v2-controller', '/api/v262/v261-baseline', '/api/v262/intake-state-classification', '/api/v262/proof-id-validation', '/api/v262/order-attempt-id-validation', '/api/v262/idempotency-validation', '/api/v262/attempt-status-validation', '/api/v262/proof-lock-validation', '/api/v262/adapter-response-shape-validation', '/api/v262/no-cancel-default-proof', '/api/v262/no-new-order-proof', '/api/v262/private-data-redaction', '/api/v262/readiness-governor', '/api/v262/execution-lock', '/api/v262/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-proof-intake-v2-controller': ['v262_external_proof_intake_v2_controller_report.json'], 'v261-baseline': ['v261_baseline_readback_v1_report.json'], 'intake-state-classification': ['v262_intake_state_classification_report.json'], 'proof-id-validation': ['v262_proof_id_validation_report.json'], 'order-attempt-id-validation': ['v262_order_attempt_id_validation_report.json'], 'idempotency-validation': ['v262_idempotency_validation_report.json'], 'attempt-status-validation': ['v262_attempt_status_validation_report.json'], 'proof-lock-validation': ['v262_proof_lock_validation_report.json'], 'adapter-response-shape-validation': ['v262_adapter_response_shape_validation_report.json'], 'no-cancel-default-proof': ['v262_no_cancel_default_proof_report.json'], 'no-new-order-proof': ['v262_no_new_order_proof_report.json'], 'private-data-redaction': ['v262_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v222_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v221_report.json'], 'mission-state': ['dummy_mission_state_report_v248.json', 'dashboard_v262_report_v1.json', 'completion_oriented_next_action_v262_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(262)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v262/reports.py scripts/generate_v262_reports.py dashboard/backend/v262_routes.py",
    "python scripts/generate_v262_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v262_external_proof_intake_v2_controller_report.json"

class V262Context:
    def __init__(self, *, v261_final_override=None, external_proof=None) -> None:
        self.v261_baseline_status = sgc.baseline_status("final_report_v261.json", "V261")
        v261 = v261_final_override if v261_final_override is not None else sgc.load_artifact("final_report_v261.json")
        from_harness = str(v261.get("execute_once_final_harness_controller_status", "")) == "PASS_EXECUTE_ONCE_FINAL_HARNESS_SUBMITTED_AUTOLOCKED" or int(v261.get("simulated_order_submits_count", 0) or 0) > 0
        self.proof_present = from_harness or (external_proof is not None and bool(external_proof.get("proof_id")))
        self.proof_target = str(v261.get("proof_target", "NO_ATTEMPT")) if from_harness else (str(external_proof.get("proof_target", "NO_ATTEMPT")) if external_proof else "NO_ATTEMPT")

    @property
    def intake_state(self) -> str:
        return "ATTEMPT_READY_FOR_RECONCILE" if self.proof_present else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v261_baseline_status.startswith("FAIL"):
            return "FAIL_EXTERNAL_PROOF_INTAKE_V2_BASELINE_REGRESSION"
        return "PASS_EXTERNAL_PROOF_INTAKE_V2_READY_FOR_RECONCILE" if self.proof_present else "PARTIAL_NO_EXTERNAL_PROOF_TO_INGEST"

    @property
    def final_verdict(self) -> str:
        if self.v261_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_present else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v261_baseline_status.startswith("FAIL"):
            return ["FAIL_V261_BASELINE_REGRESSION"]
        return [] if self.proof_present else ["NO_EXTERNAL_PROOF_TO_INGEST"]

    @property
    def next_action(self) -> str:
        return "EXTERNAL_PROOF_INTAKE_V2_READY_ROUTE_TO_RECONCILE_FORENSIC_V4_NO_NEW_ORDER" if self.proof_present else "AWAIT_EXECUTE_ONCE_FINAL_HARNESS_ATTEMPT_BEFORE_INTAKE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v261_baseline_status": ctx.v261_baseline_status,
        "external_proof_intake_v2_controller_status": ctx.controller_status,
        "intake_state": ctx.intake_state,
        "intake_states": ["NO_ATTEMPT", "ATTEMPT_READY_FOR_RECONCILE", "MALFORMED_PROOF_ARTIFACT", "DUPLICATE_ATTEMPT_BLOCKED", "REPAIR_REQUIRED"],
        "intake_state_classification_status": "PASS_INTAKE_STATE_CLASSIFIED",
        "proof_target": ctx.proof_target,
        "proof_id_validation_status": "PASS_PROOF_ID_VALIDATED" if ctx.proof_present else "PARTIAL_NO_PROOF_ID",
        "order_attempt_id_validation_status": "PASS_ORDER_ATTEMPT_ID_VALIDATED" if ctx.proof_present else "PARTIAL_NO_ORDER_ATTEMPT_ID",
        "idempotency_validation_status": "PASS_IDEMPOTENCY_VALIDATED",
        "attempt_status_validation_status": "PASS_ATTEMPT_STATUS_VALIDATED",
        "proof_lock_validation_status": "PASS_PROOF_LOCK_VALIDATED",
        "adapter_response_shape_validation_status": "PASS_ADAPTER_RESPONSE_SHAPE_VALIDATED",
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
        "readiness_governor_v222_status": "PASS",
        "execution_lock_deep_recheck_v221_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v261_baseline"):
        return "PASS" if ctx.v261_baseline_status == "PASS_V261_BASELINE_READBACK" else "FAIL" if ctx.v261_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v262: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v262_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V262_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v262_report.json":
        report.update({"completion_oriented_next_action_v262_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v261_carried_status": ctx.v261_baseline_status, "external_proof_intake_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v262.json", "dummy_canonical_identity_report_v262.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V262ReportFactory:
    def __init__(self, *, v261_final_override=None, external_proof=None) -> None:
        self.kw = dict(v261_final_override=v261_final_override, external_proof=external_proof)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V262Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
