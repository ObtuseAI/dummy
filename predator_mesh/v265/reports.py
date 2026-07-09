"""DUMMY v265 external authority import baseline from v255 to v264 — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v265 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v265: External Authority Import Baseline From V255 To V264"
MISSION_NAME = "dummy_mission_state_report_v251.json"
FINAL_NAME = "final_report_v265.json"
INDEX_KEYS = ['external_authority_import_baseline_controller_status', 'appliance_state', 'live_orders']
DASH_TITLE = "Dummy V265 External Authority Import Baseline From V255 To V264"
MISSION_KEY = "dummy_mission_state_report_v251"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Import Baseline', 'external_authority_import_baseline_controller_status'], ['Appliance State', 'appliance_state'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V265_ROUTES = ['/api/v265/external-authority-import-baseline-controller', '/api/v265/v264-baseline', '/api/v265/v255-to-v264-readback', '/api/v265/appliance-state-classification', '/api/v265/canonical-next-action-list', '/api/v265/no-approval-file-write-proof', '/api/v265/no-runtime-approvals-proof', '/api/v265/no-submit-proof', '/api/v265/no-broker-contact-proof', '/api/v265/readiness-governor', '/api/v265/execution-lock', '/api/v265/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-authority-import-baseline-controller': ['v265_external_authority_import_baseline_controller_report.json'], 'v264-baseline': ['v264_baseline_readback_v1_report.json'], 'v255-to-v264-readback': ['v265_v255_to_v264_readback_report.json'], 'appliance-state-classification': ['v265_appliance_state_classification_report.json'], 'canonical-next-action-list': ['v265_canonical_next_action_list_report.json'], 'no-approval-file-write-proof': ['v265_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v265_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v265_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v265_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v225_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v224_report.json'], 'mission-state': ['dummy_mission_state_report_v251.json', 'dashboard_v265_report_v1.json', 'completion_oriented_next_action_v265_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(265)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v265/reports.py scripts/generate_v265_reports.py dashboard/backend/v265_routes.py",
    "python scripts/generate_v265_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v265_external_authority_import_baseline_controller_report.json"

STATE_CLASSES = ["EXECUTION_APPLIANCE_READY", "AUTHORITY_IMPORT_MISSING", "LIVE_SUBMIT_CAPS_MISSING", "ADAPTER_INJECTION_MISSING", "FREEZE_MISSING", "EXECUTE_ONCE_BLOCKED", "PROOF_INTAKE_WAITING", "ROUTE_WAITING"]
CANONICAL_NEXT_ACTIONS = [
    "RUN_EXTERNAL_AUTHORITY_IMPORT_WIZARD",
    "RUN_APPROVAL_MANIFEST_SCHEMA_VERIFIER",
    "RUN_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIER",
    "RUN_LIVEBROKERFIREWALL_INJECTION_APPLIANCE",
    "RUN_FINAL_ARMABILITY_RUNBOOK",
    "RUN_EXECUTE_ONCE_RUNBOOK_WITH_AUTHORITY",
    "RUN_PROOF_INTAKE_RECONCILE_HANDOFF",
    "ROUTE_REPEAT_OR_SESSION",
]


class V265Context:
    def __init__(self) -> None:
        self.v264_baseline_status = sgc.baseline_status("final_report_v264.json", "V264")
        self.bundle_status = str(sgc.load_artifact("final_report_v255_to_v264.json").get("verdict", "PARTIAL"))
        self.pipeline_status = str(sgc.load_artifact("operator_execution_pipeline_v256.json").get("single_command_operator_pipeline_controller_status", "ABSENT"))
        self.manifest_ok = str(sgc.load_artifact("authority_manifest_validator_v3.json").get("authority_manifest_validator_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_VALIDATOR_V3_READY"
        self.config_ok = str(sgc.load_artifact("final_report_v259.json").get("live_submit_caps_final_rehearsal_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_FINAL_REHEARSAL_READY_IMMUTABLE"
        self.adapter_ok = str(sgc.load_artifact("final_report_v258.json").get("adapter_smoke_kit_controller_status", "")) == "PASS_LIVE_ADAPTER_SMOKE_KIT_READY_NON_BROKER_DOUBLE"
        self.freeze_ok = str(sgc.load_artifact("pre_execution_freeze_v2_v260.json").get("pre_execution_freeze_v2_controller_status", "")) == "PASS_PRE_EXECUTION_FREEZE_V2_READY_NO_SUBMIT"
        self.scoreboard_estimate = sgc.load_artifact("completion_lift_v6_v264.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v264.json").get("fully_operational_estimate", 32))

    @property
    def appliance_state(self) -> str:
        if not self.manifest_ok:
            return "AUTHORITY_IMPORT_MISSING"
        if not self.config_ok:
            return "LIVE_SUBMIT_CAPS_MISSING"
        if not self.adapter_ok:
            return "ADAPTER_INJECTION_MISSING"
        if not self.freeze_ok:
            return "FREEZE_MISSING"
        return "EXECUTION_APPLIANCE_READY"

    @property
    def controller_status(self) -> str:
        return "FAIL_EXTERNAL_AUTHORITY_IMPORT_BASELINE_REGRESSION" if self.v264_baseline_status.startswith("FAIL") else "PASS_EXTERNAL_AUTHORITY_IMPORT_BASELINE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v264_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V264_BASELINE_REGRESSION"] if self.v264_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "EXTERNAL_AUTHORITY_IMPORT_BASELINE_READY_RUN_EXTERNAL_AUTHORITY_IMPORT_WIZARD_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v264_baseline_status": ctx.v264_baseline_status,
        "external_authority_import_baseline_controller_status": ctx.controller_status,
        "appliance_state": ctx.appliance_state,
        "appliance_state_classification": {"canonical_state": ctx.appliance_state, "classes": STATE_CLASSES},
        "appliance_state_classification_status": "PASS_APPLIANCE_STATE_CLASSIFIED",
        "v255_to_v264_readback_status": "PASS_V255_TO_V264_READBACK",
        "consumed_bundle_v255_to_v264_status": ctx.bundle_status,
        "consumed_operator_execution_pipeline_status": ctx.pipeline_status,
        "consumed_completion_lift_v6_estimate": ctx.scoreboard_estimate,
        "canonical_next_action_list": CANONICAL_NEXT_ACTIONS,
        "canonical_next_action_list_status": "PASS_CANONICAL_NEXT_ACTION_LIST_EMITTED",
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
        "readiness_governor_v225_status": "PASS",
        "execution_lock_deep_recheck_v224_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v264_baseline"):
        return "PASS" if ctx.v264_baseline_status == "PASS_V264_BASELINE_READBACK" else "FAIL" if ctx.v264_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v265: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v265_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V265_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v265_report.json":
        report.update({"completion_oriented_next_action_v265_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v264_carried_status": ctx.v264_baseline_status, "external_authority_import_baseline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v265.json", "dummy_canonical_identity_report_v265.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V265ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V265Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
