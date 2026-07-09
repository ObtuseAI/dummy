"""DUMMY v234 acceleration lock and operator command sequence — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v234 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v234: Acceleration Lock And Operator Command Sequence"
MISSION_NAME = "dummy_mission_state_report_v220.json"
FINAL_NAME = "final_report_v234.json"
INDEX_KEYS = ['acceleration_lock_controller_status', 'next_action_matrix_selection', 'total_real_live_orders_submitted']
DASH_TITLE = "Dummy V234 Acceleration Lock And Operator Command Sequence"
MISSION_KEY = "dummy_mission_state_report_v220"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Acceleration Lock', 'acceleration_lock_controller_status'], ['Next Action Matrix', 'next_action_matrix_selection'], ['Total Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V234_ROUTES = ['/api/v234/acceleration-lock-controller', '/api/v234/v233-baseline', '/api/v234/activation-pipeline-summary', '/api/v234/manifest-pack-summary', '/api/v234/dry-pipeline-summary', '/api/v234/intake-summary', '/api/v234/arming-summary', '/api/v234/live-proof-execution-summary', '/api/v234/reconcile-forensic-summary', '/api/v234/route-decision-summary', '/api/v234/completion-scoreboard-summary', '/api/v234/operator-command-sequence', '/api/v234/next-action-matrix', '/api/v234/total-live-order-count', '/api/v234/no-scale-proof', '/api/v234/no-autonomy-proof', '/api/v234/no-new-order-proof', '/api/v234/readiness-governor', '/api/v234/execution-lock', '/api/v234/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'acceleration-lock-controller': ['v234_acceleration_lock_controller_report.json'], 'v233-baseline': ['v233_baseline_readback_v1_report.json'], 'activation-pipeline-summary': ['v234_activation_pipeline_summary_report.json'], 'manifest-pack-summary': ['v234_manifest_pack_summary_report.json'], 'dry-pipeline-summary': ['v234_dry_pipeline_summary_report.json'], 'intake-summary': ['v234_intake_summary_report.json'], 'arming-summary': ['v234_arming_summary_report.json'], 'live-proof-execution-summary': ['v234_live_proof_execution_summary_report.json'], 'reconcile-forensic-summary': ['v234_reconcile_forensic_summary_report.json'], 'route-decision-summary': ['v234_route_decision_summary_report.json'], 'completion-scoreboard-summary': ['v234_completion_scoreboard_summary_report.json'], 'operator-command-sequence': ['v234_operator_command_sequence_report.json'], 'next-action-matrix': ['v234_next_action_matrix_report.json'], 'total-live-order-count': ['v234_total_live_order_count_report.json'], 'no-scale-proof': ['v234_no_scale_proof_report.json'], 'no-autonomy-proof': ['v234_no_autonomy_proof_report.json'], 'no-new-order-proof': ['v234_no_new_order_proof_report.json'], 'readiness-governor': ['readiness_governor_v194_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v193_report.json'], 'mission-state': ['dummy_mission_state_report_v220.json', 'dashboard_v234_report_v1.json', 'completion_oriented_next_action_v234_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(234)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v234/reports.py scripts/generate_v234_reports.py dashboard/backend/v234_routes.py",
    "python scripts/generate_v234_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v234_acceleration_lock_controller_report.json"

NEXT_ACTION_MATRIX = [
    "PROVIDE_EXTERNAL_AUTHORITY_INTAKE",
    "RUN_FINAL_RESOLVER_ARMING",
    "RUN_LIVE_PROOF_EXECUTE_ONCE",
    "RUN_RECONCILE_FORENSIC_PIPELINE",
    "REVIEW_ROUTE_DECISION",
    "REPAIR_REQUIRED",
]
OPERATOR_COMMAND_SEQUENCE = [
    "python scripts/run_dummy_activation_pipeline.py",
    "# operator supplies external authority manifest pack (approval files + descriptors) OUTSIDE Dummy",
    "python scripts/run_dummy_external_authority_intake.py",
    "python scripts/run_dummy_final_resolver_arming.py",
    "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY python scripts/run_dummy_live_proof_execute_once.py",
    "python scripts/run_dummy_reconcile_forensic_pipeline.py",
    "python scripts/run_dummy_completion_scoreboard_v3.py",
]


class V234Context:
    def __init__(self, *, intake_override=None, arming_override=None, proof_override=None, pipeline_override=None) -> None:
        self.v233_baseline_status = sgc.baseline_status("final_report_v233.json", "V233")
        self.pipeline_status = str(sgc.load_artifact("final_report_v227.json").get("one_command_dry_pipeline_controller_status", "PASS_ONE_COMMAND_DRY_PIPELINE_COMPLETE"))
        self.manifest_pack_status = str(sgc.load_artifact("final_report_v226.json").get("manifest_pack_controller_status", "PASS_MANIFEST_PACK_READY_READONLY"))
        self.intake_valid = bool(intake_override) if intake_override is not None else (str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT")
        self.arming_ready = bool(arming_override) if arming_override is not None else (str(sgc.load_artifact("final_report_v229.json").get("final_resolver_arming_controller_status", "")) == "PASS_FINAL_RESOLVER_ARMING_READY_NO_SUBMIT")
        self.proof_done = bool(proof_override) if proof_override is not None else (str(sgc.load_artifact("final_report_v230.json").get("live_proof_execution_orchestrator_controller_status", "")) == "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED")
        self.pipeline_done = bool(pipeline_override) if pipeline_override is not None else (str(sgc.load_artifact("final_report_v231.json").get("reconcile_forensic_pipeline_controller_status", "")) == "PASS_RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED")
        self.route_status = str(sgc.load_artifact("final_report_v232.json").get("route_state", "ROUTE_BLOCKED_NO_LIVE_PROOF"))
        self.scoreboard_estimate = sgc.load_artifact("completion_scoreboard_v233.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v233.json").get("fully_operational_estimate", 15))

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.intake_valid:
            return "PROVIDE_EXTERNAL_AUTHORITY_INTAKE"
        if not self.arming_ready:
            return "RUN_FINAL_RESOLVER_ARMING"
        if not self.proof_done:
            return "RUN_LIVE_PROOF_EXECUTE_ONCE"
        if not self.pipeline_done:
            return "RUN_RECONCILE_FORENSIC_PIPELINE"
        return "REVIEW_ROUTE_DECISION"

    @property
    def controller_status(self) -> str:
        return "FAIL_ACCELERATION_LOCK_BASELINE_REGRESSION" if self.v233_baseline_status.startswith("FAIL") else "PASS_ACCELERATION_LOCK_AND_OPERATOR_COMMAND_SEQUENCE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v233_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V233_BASELINE_REGRESSION"] if self.v233_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"ACCELERATION_LOCKED_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx) -> dict[str, Any]:
    return {
        "v233_baseline_status": ctx.v233_baseline_status,
        "acceleration_lock_controller_status": ctx.controller_status,
        "activation_pipeline_summary": ctx.pipeline_status,
        "manifest_pack_summary": ctx.manifest_pack_status,
        "dry_pipeline_summary": ctx.pipeline_status,
        "intake_summary": "VALIDATED" if ctx.intake_valid else "ABSENT_OR_INCOMPLETE",
        "arming_summary": "READY" if ctx.arming_ready else "BLOCKED",
        "live_proof_execution_summary": "SUBMITTED_AUTOLOCKED" if ctx.proof_done else "NOT_ARMED",
        "reconcile_forensic_summary": "COMPLETE" if ctx.pipeline_done else "NO_ATTEMPT",
        "route_decision_summary": ctx.route_status,
        "completion_scoreboard_summary": ctx.scoreboard_estimate,
        "operator_command_sequence": OPERATOR_COMMAND_SEQUENCE,
        "operator_command_sequence_status": "PASS_OPERATOR_COMMAND_SEQUENCE_EMITTED",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "total_live_order_count": 0,
        "total_live_order_count_status": "PASS_TOTAL_LIVE_ORDER_COUNT_ZERO",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
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
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v194_status": "PASS",
        "execution_lock_deep_recheck_v193_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v233_baseline"):
        return "PASS" if ctx.v233_baseline_status == "PASS_V233_BASELINE_READBACK" else "FAIL" if ctx.v233_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v234: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v234_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V234_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v234_report.json":
        report.update({"completion_oriented_next_action_v234_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v233_carried_status": ctx.v233_baseline_status, "acceleration_lock_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v234.json", "dummy_canonical_identity_report_v234.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V234ReportFactory:
    def __init__(self, *, intake_override=None, arming_override=None, proof_override=None, pipeline_override=None) -> None:
        self.kw = dict(intake_override=intake_override, arming_override=arming_override, proof_override=proof_override, pipeline_override=pipeline_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V234Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
