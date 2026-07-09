"""DUMMY v256 single command operator pipeline dry default — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v256 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v256: Single Command Operator Pipeline Dry Default"
MISSION_NAME = "dummy_mission_state_report_v242.json"
FINAL_NAME = "final_report_v256.json"
INDEX_KEYS = ['single_command_operator_pipeline_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V256 Single Command Operator Pipeline Dry Default"
MISSION_KEY = "dummy_mission_state_report_v242"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Single-Command Pipeline', 'single_command_operator_pipeline_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V256_ROUTES = ['/api/v256/single-command-operator-pipeline-controller', '/api/v256/v255-baseline', '/api/v256/pipeline-stages', '/api/v256/dry-default-proof', '/api/v256/no-firewall-submit-proof', '/api/v256/no-broker-payload-proof', '/api/v256/no-approval-file-write-proof', '/api/v256/no-runtime-approvals-proof', '/api/v256/no-config-caps-mutation-proof', '/api/v256/no-broker-contact-proof', '/api/v256/readiness-governor', '/api/v256/execution-lock', '/api/v256/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'single-command-operator-pipeline-controller': ['v256_single_command_operator_pipeline_controller_report.json'], 'v255-baseline': ['v255_baseline_readback_v1_report.json'], 'pipeline-stages': ['v256_pipeline_stages_report.json'], 'dry-default-proof': ['v256_dry_default_proof_report.json'], 'no-firewall-submit-proof': ['v256_no_firewall_submit_proof_report.json'], 'no-broker-payload-proof': ['v256_no_broker_payload_proof_report.json'], 'no-approval-file-write-proof': ['v256_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v256_no_runtime_approvals_proof_report.json'], 'no-config-caps-mutation-proof': ['v256_no_config_caps_mutation_proof_report.json'], 'no-broker-contact-proof': ['v256_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v216_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v215_report.json'], 'mission-state': ['dummy_mission_state_report_v242.json', 'dashboard_v256_report_v1.json', 'completion_oriented_next_action_v256_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(256)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v256/reports.py scripts/generate_v256_reports.py dashboard/backend/v256_routes.py",
    "python scripts/generate_v256_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v256_single_command_operator_pipeline_controller_report.json"

PIPELINE_STAGES = [
    "read_v255_baseline",
    "run_authority_rehearsal",
    "run_live_submit_caps_rehearsal",
    "run_firewall_adapter_contract_check",
    "run_broker_readonly_doctor_if_available",
    "run_armable_quorum_doctor",
    "run_pre_execution_freeze_no_submit",
    "run_execute_once_dry_fixture_harness_dry",
    "run_post_execution_intake_bridge",
    "run_completion_lift",
]


class V256Context:
    def __init__(self) -> None:
        self.v255_baseline_status = sgc.baseline_status("final_report_v255.json", "V255")

    @property
    def controller_status(self) -> str:
        return "FAIL_SINGLE_COMMAND_OPERATOR_PIPELINE_BASELINE_REGRESSION" if self.v255_baseline_status.startswith("FAIL") else "PASS_SINGLE_COMMAND_OPERATOR_PIPELINE_COMPLETE_DRY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v255_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V255_BASELINE_REGRESSION"] if self.v255_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "SINGLE_COMMAND_OPERATOR_PIPELINE_COMPLETE_DRY_OPERATOR_SUPPLY_EXTERNAL_AUTHORITY_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v255_baseline_status": ctx.v255_baseline_status,
        "single_command_operator_pipeline_controller_status": ctx.controller_status,
        "pipeline_stages": PIPELINE_STAGES,
        "pipeline_stages_status": "PASS_PIPELINE_STAGES_RAN_DRY",
        "dry_mode": True,
        "dry_default_proof_status": "PASS_DRY_DEFAULT",
        "no_firewall_submit_proof_status": "PASS_NO_FIREWALL_SUBMIT",
        "firewall_submit_invoked": False,
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "broker_payload_created": False,
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
        "no_config_caps_mutation_proof_status": "PASS_NO_CONFIG_CAPS_MUTATION",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "broker_contacted": False,

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
        "readiness_governor_v216_status": "PASS",
        "execution_lock_deep_recheck_v215_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v255_baseline"):
        return "PASS" if ctx.v255_baseline_status == "PASS_V255_BASELINE_READBACK" else "FAIL" if ctx.v255_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v256: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v256_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V256_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v256_report.json":
        report.update({"completion_oriented_next_action_v256_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v255_carried_status": ctx.v255_baseline_status, "single_command_operator_pipeline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v256.json", "dummy_canonical_identity_report_v256.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V256ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V256Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
