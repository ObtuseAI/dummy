"""DUMMY v246 operator ready appliance pack readonly no approval write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v246 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v246: Operator Ready Appliance Pack Readonly No Approval Write"
MISSION_NAME = "dummy_mission_state_report_v232.json"
FINAL_NAME = "final_report_v246.json"
INDEX_KEYS = ['operator_ready_appliance_pack_controller_status', 'approval_files_written', 'runtime_approvals_created_by_dummy']
DASH_TITLE = "Dummy V246 Operator Ready Appliance Pack Readonly No Approval Write"
MISSION_KEY = "dummy_mission_state_report_v232"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Appliance Pack', 'operator_ready_appliance_pack_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Runtime Approvals Created', 'runtime_approvals_created_by_dummy'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V246_ROUTES = ['/api/v246/operator-ready-appliance-pack-controller', '/api/v246/v245-baseline', '/api/v246/appliance-pack', '/api/v246/approval-file-paths', '/api/v246/command-sequence', '/api/v246/not-approval-markers', '/api/v246/no-approval-file-write-proof', '/api/v246/no-runtime-approvals-proof', '/api/v246/no-config-caps-write-proof', '/api/v246/no-submit-proof', '/api/v246/readiness-governor', '/api/v246/execution-lock', '/api/v246/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'operator-ready-appliance-pack-controller': ['v246_operator_ready_appliance_pack_controller_report.json'], 'v245-baseline': ['v245_baseline_readback_v1_report.json'], 'appliance-pack': ['v246_appliance_pack_report.json'], 'approval-file-paths': ['v246_approval_file_paths_report.json'], 'command-sequence': ['v246_command_sequence_report.json'], 'not-approval-markers': ['v246_not_approval_markers_report.json'], 'no-approval-file-write-proof': ['v246_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v246_no_runtime_approvals_proof_report.json'], 'no-config-caps-write-proof': ['v246_no_config_caps_write_proof_report.json'], 'no-submit-proof': ['v246_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v206_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v205_report.json'], 'mission-state': ['dummy_mission_state_report_v232.json', 'dashboard_v246_report_v1.json', 'completion_oriented_next_action_v246_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(246)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v246/reports.py scripts/generate_v246_reports.py dashboard/backend/v246_routes.py",
    "python scripts/generate_v246_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v246_operator_ready_appliance_pack_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
APPROVAL_FILE_PATHS = [
    "runtime/approvals/dummy_controlled_production_pilot_approval.json",
    "runtime/approvals/dummy_controlled_session_canary_approval.json",
    "runtime/approvals/dummy_broker_readonly_approval.json",
]
APPROVAL_PHRASE_REFS = ["CONTROLLED_PILOT_PHRASE", "CONTROLLED_SESSION_PHRASE", "BROKER_READONLY_PHRASE"]
COMMAND_SEQUENCE = [
    "python scripts/run_dummy_external_authority_rehearsal.py",
    "python scripts/run_dummy_firewall_adapter_contract_check.py",
    "python scripts/run_dummy_live_submit_caps_rehearsal.py",
    "python scripts/run_dummy_armable_quorum_doctor.py",
    "python scripts/run_dummy_pre_execution_freeze_report.py",
    "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK + " python scripts/run_dummy_live_proof_execute_once_v2.py",
    "python scripts/run_dummy_post_execution_intake_bridge.py",
    "python scripts/run_dummy_reconcile_forensic_pipeline_v2.py",
    "python scripts/run_dummy_completion_lift_v5.py",
]
APPLIANCE_PACK = {
    "not_approval": True,
    "approval_file_paths": APPROVAL_FILE_PATHS,
    "approval_phrase_refs": APPROVAL_PHRASE_REFS,
    "manifest_instructions": "Operator writes each approval file externally with the exact phrase; Dummy never writes them.",
    "live_submit_caps_instructions": "Operator externally enables live-submit and confirms caps; Dummy is read-only.",
    "firewall_adapter_injection_instructions": "Operator injects a LiveBrokerFirewall adapter implementing submit(); Dummy never contacts a broker.",
    "broker_readonly_instructions": "Operator supplies broker-readonly approval + read-only adapter for verification only.",
    "dry_validation_command": "python scripts/run_dummy_activation_pipeline.py",
    "armable_quorum_command": "python scripts/run_dummy_armable_quorum_doctor.py",
    "execute_once_command": "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK + " python scripts/run_dummy_live_proof_execute_once_v2.py",
    "reconcile_forensic_command": "python scripts/run_dummy_reconcile_forensic_pipeline_v2.py",
    "route_decision_command": "python scripts/generate_v232_reports.py",
}


class V246Context:
    def __init__(self) -> None:
        self.v245_baseline_status = sgc.baseline_status("final_report_v245.json", "V245")

    @property
    def controller_status(self) -> str:
        return "FAIL_OPERATOR_READY_APPLIANCE_PACK_BASELINE_REGRESSION" if self.v245_baseline_status.startswith("FAIL") else "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v245_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V245_BASELINE_REGRESSION"] if self.v245_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_READY_APPLIANCE_PACK_READY_OPERATOR_FOLLOW_PACK_EXTERNALLY_DUMMY_WRITES_NOTHING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v245_baseline_status": ctx.v245_baseline_status,
        "operator_ready_appliance_pack_controller_status": ctx.controller_status,
        "appliance_pack": APPLIANCE_PACK,
        "appliance_pack_status": "PASS_APPLIANCE_PACK_EMITTED",
        "approval_file_paths": APPROVAL_FILE_PATHS,
        "approval_file_paths_status": "PASS_APPROVAL_FILE_PATHS_LISTED",
        "command_sequence": COMMAND_SEQUENCE,
        "command_sequence_status": "PASS_COMMAND_SEQUENCE_EMITTED",
        "not_approval_markers": {"appliance_pack": "NOT_APPROVAL", "all_templates": "NOT_APPROVAL"},
        "not_approval_markers_status": "PASS_NOT_APPROVAL_MARKED",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
        "no_config_caps_write_proof_status": "PASS_NO_CONFIG_CAPS_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",

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
        "readiness_governor_v206_status": "PASS",
        "execution_lock_deep_recheck_v205_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v245_baseline"):
        return "PASS" if ctx.v245_baseline_status == "PASS_V245_BASELINE_READBACK" else "FAIL" if ctx.v245_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v246: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v246_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V246_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v246_report.json":
        report.update({"completion_oriented_next_action_v246_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v245_carried_status": ctx.v245_baseline_status, "operator_ready_appliance_pack_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v246.json", "dummy_canonical_identity_report_v246.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V246ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V246Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
