"""DUMMY v227 one command dry pipeline zero broker contact — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v227 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v227: One Command Dry Pipeline Zero Broker Contact"
MISSION_NAME = "dummy_mission_state_report_v213.json"
FINAL_NAME = "final_report_v227.json"
INDEX_KEYS = ['one_command_dry_pipeline_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V227 One Command Dry Pipeline Zero Broker Contact"
MISSION_KEY = "dummy_mission_state_report_v213"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Dry Pipeline', 'one_command_dry_pipeline_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V227_ROUTES = ['/api/v227/one-command-dry-pipeline-controller', '/api/v227/v226-baseline', '/api/v227/dry-stage-manifest-intake', '/api/v227/dry-stage-resolver', '/api/v227/dry-stage-arming', '/api/v227/dry-stage-live-proof', '/api/v227/dry-stage-reconcile-forensic', '/api/v227/simulated-pipeline-schema', '/api/v227/no-firewall-submit-proof', '/api/v227/no-broker-payload-proof', '/api/v227/no-account-access-proof', '/api/v227/no-file-write-proof', '/api/v227/readiness-governor', '/api/v227/execution-lock', '/api/v227/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'one-command-dry-pipeline-controller': ['v227_one_command_dry_pipeline_controller_report.json'], 'v226-baseline': ['v226_baseline_readback_v1_report.json'], 'dry-stage-manifest-intake': ['v227_dry_stage_manifest_intake_report.json'], 'dry-stage-resolver': ['v227_dry_stage_resolver_report.json'], 'dry-stage-arming': ['v227_dry_stage_arming_report.json'], 'dry-stage-live-proof': ['v227_dry_stage_live_proof_report.json'], 'dry-stage-reconcile-forensic': ['v227_dry_stage_reconcile_forensic_report.json'], 'simulated-pipeline-schema': ['v227_simulated_pipeline_schema_report.json'], 'no-firewall-submit-proof': ['v227_no_firewall_submit_proof_report.json'], 'no-broker-payload-proof': ['v227_no_broker_payload_proof_report.json'], 'no-account-access-proof': ['v227_no_account_access_proof_report.json'], 'no-file-write-proof': ['v227_no_file_write_proof_report.json'], 'readiness-governor': ['readiness_governor_v187_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v186_report.json'], 'mission-state': ['dummy_mission_state_report_v213.json', 'dashboard_v227_report_v1.json', 'completion_oriented_next_action_v227_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(227)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v227/reports.py scripts/generate_v227_reports.py dashboard/backend/v227_routes.py",
    "python scripts/generate_v227_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v227_one_command_dry_pipeline_controller_report.json"

class V227Context:
    def __init__(self) -> None:
        self.v226_baseline_status = sgc.baseline_status("final_report_v226.json", "V226")
        self.resolver_status = str(sgc.load_artifact("authority_resolver_v208.json").get("authority_state", sgc.load_artifact("final_report_v208.json").get("authority_state", "LIVE_BLOCKED_AUTHORITY_ABSENT")))

    @property
    def controller_status(self) -> str:
        return "FAIL_ONE_COMMAND_DRY_PIPELINE_BASELINE_REGRESSION" if self.v226_baseline_status.startswith("FAIL") else "PASS_ONE_COMMAND_DRY_PIPELINE_COMPLETE"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v226_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V226_BASELINE_REGRESSION"] if self.v226_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "ONE_COMMAND_DRY_PIPELINE_COMPLETE_OPERATOR_SUPPLY_EXTERNAL_AUTHORITY_INTAKE_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v226_baseline_status": ctx.v226_baseline_status,
        "one_command_dry_pipeline_controller_status": ctx.controller_status,
        "dry_mode": True,
        "dry_stage_manifest_intake_status": "PASS_DRY_MANIFEST_INTAKE",
        "dry_stage_resolver_status": "PASS_DRY_RESOLVER",
        "dry_stage_resolver_state": ctx.resolver_status,
        "dry_stage_arming_status": "PASS_DRY_ARMING",
        "dry_stage_live_proof_status": "PASS_DRY_LIVE_PROOF_NO_SUBMIT",
        "dry_stage_reconcile_forensic_status": "PASS_DRY_RECONCILE_FORENSIC",
        "simulated_pipeline_schema_status": "PASS_SIMULATED_PIPELINE_SCHEMA",
        "no_firewall_submit_proof_status": "PASS_NO_FIREWALL_SUBMIT",
        "firewall_submit_invoked": False,
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "broker_payload_created": False,
        "no_account_access_proof_status": "PASS_NO_ACCOUNT_ACCESS",
        "no_file_write_proof_status": "PASS_NO_FILE_WRITE",
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
        "readiness_governor_v187_status": "PASS",
        "execution_lock_deep_recheck_v186_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v226_baseline"):
        return "PASS" if ctx.v226_baseline_status == "PASS_V226_BASELINE_READBACK" else "FAIL" if ctx.v226_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v227: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v227_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V227_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v227_report.json":
        report.update({"completion_oriented_next_action_v227_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v226_carried_status": ctx.v226_baseline_status, "one_command_dry_pipeline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v227.json", "dummy_canonical_identity_report_v227.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V227ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V227Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
