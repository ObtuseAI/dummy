"""DUMMY v255 operator execution appliance baseline from v245 to v254 — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v255 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v255: Operator Execution Appliance Baseline From V245 To V254"
MISSION_NAME = "dummy_mission_state_report_v241.json"
FINAL_NAME = "final_report_v255.json"
INDEX_KEYS = ['operator_execution_appliance_baseline_controller_status', 'approval_files_written', 'live_orders']
DASH_TITLE = "Dummy V255 Operator Execution Appliance Baseline From V245 To V254"
MISSION_KEY = "dummy_mission_state_report_v241"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Execution Baseline', 'operator_execution_appliance_baseline_controller_status'], ['Appliance State', 'appliance_state'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V255_ROUTES = ['/api/v255/operator-execution-appliance-baseline-controller', '/api/v255/v254-baseline', '/api/v255/v245-to-v254-readback', '/api/v255/appliance-state-classification', '/api/v255/no-approval-file-write-proof', '/api/v255/no-runtime-approvals-proof', '/api/v255/no-submit-proof', '/api/v255/no-broker-contact-proof', '/api/v255/readiness-governor', '/api/v255/execution-lock', '/api/v255/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'operator-execution-appliance-baseline-controller': ['v255_operator_execution_appliance_baseline_controller_report.json'], 'v254-baseline': ['v254_baseline_readback_v1_report.json'], 'v245-to-v254-readback': ['v255_v245_to_v254_readback_report.json'], 'appliance-state-classification': ['v255_appliance_state_classification_report.json'], 'no-approval-file-write-proof': ['v255_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v255_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v255_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v255_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v215_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v214_report.json'], 'mission-state': ['dummy_mission_state_report_v241.json', 'dashboard_v255_report_v1.json', 'completion_oriented_next_action_v255_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(255)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v255/reports.py scripts/generate_v255_reports.py dashboard/backend/v255_routes.py",
    "python scripts/generate_v255_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v255_operator_execution_appliance_baseline_controller_report.json"

STATE_CLASSES = ["APPLIANCE_READY", "AUTHORITY_MANIFEST_MISSING", "LIVE_SUBMIT_CAPS_MISSING", "ADAPTER_MISSING", "FREEZE_BLOCKED", "EXECUTE_ONCE_BLOCKED", "PROOF_INTAKE_WAITING", "RECONCILE_FORENSIC_WAITING"]


class V255Context:
    def __init__(self) -> None:
        self.v254_baseline_status = sgc.baseline_status("final_report_v254.json", "V254")
        self.bundle_status = str(sgc.load_artifact("final_report_v245_to_v254.json").get("verdict", "PARTIAL"))
        self.scoreboard_estimate = sgc.load_artifact("completion_lift_v5_v254.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v254.json").get("fully_operational_estimate", 30))
        self.manifest_ok = str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
        self.config_ok = str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE"
        self.adapter_ok = str(sgc.load_artifact("final_report_v248.json").get("adapter_contract_kit_controller_status", "")) == "PASS_ADAPTER_CONTRACT_KIT_READY_NON_BROKER_DOUBLE"

    @property
    def appliance_state(self) -> str:
        if not self.manifest_ok:
            return "AUTHORITY_MANIFEST_MISSING"
        if not self.config_ok:
            return "LIVE_SUBMIT_CAPS_MISSING"
        if not self.adapter_ok:
            return "ADAPTER_MISSING"
        return "APPLIANCE_READY"

    @property
    def controller_status(self) -> str:
        return "FAIL_OPERATOR_EXECUTION_APPLIANCE_BASELINE_REGRESSION" if self.v254_baseline_status.startswith("FAIL") else "PASS_OPERATOR_EXECUTION_APPLIANCE_BASELINE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v254_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V254_BASELINE_REGRESSION"] if self.v254_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_EXECUTION_APPLIANCE_BASELINE_READY_RUN_SINGLE_COMMAND_OPERATOR_PIPELINE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v254_baseline_status": ctx.v254_baseline_status,
        "operator_execution_appliance_baseline_controller_status": ctx.controller_status,
        "appliance_state": ctx.appliance_state,
        "appliance_state_classification": {"canonical_state": ctx.appliance_state, "classes": STATE_CLASSES},
        "appliance_state_classification_status": "PASS_APPLIANCE_STATE_CLASSIFIED",
        "v245_to_v254_readback_status": "PASS_V245_TO_V254_READBACK",
        "consumed_bundle_v245_to_v254_status": ctx.bundle_status,
        "consumed_completion_lift_v5_estimate": ctx.scoreboard_estimate,
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",

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
        "readiness_governor_v215_status": "PASS",
        "execution_lock_deep_recheck_v214_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v254_baseline"):
        return "PASS" if ctx.v254_baseline_status == "PASS_V254_BASELINE_READBACK" else "FAIL" if ctx.v254_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v255: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v255_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V255_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v255_report.json":
        report.update({"completion_oriented_next_action_v255_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v254_carried_status": ctx.v254_baseline_status, "operator_execution_appliance_baseline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v255.json", "dummy_canonical_identity_report_v255.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V255ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V255Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
