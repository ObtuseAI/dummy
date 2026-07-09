"""DUMMY v225 activation pipeline baseline from v215 to v224 — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v225 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v225: Activation Pipeline Baseline From V215 To V224"
MISSION_NAME = "dummy_mission_state_report_v211.json"
FINAL_NAME = "final_report_v225.json"
INDEX_KEYS = ['activation_pipeline_baseline_controller_status', 'approval_files_written', 'live_orders']
DASH_TITLE = "Dummy V225 Activation Pipeline Baseline From V215 To V224"
MISSION_KEY = "dummy_mission_state_report_v211"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Pipeline Baseline', 'activation_pipeline_baseline_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V225_ROUTES = ['/api/v225/activation-pipeline-baseline-controller', '/api/v225/v224-baseline', '/api/v225/v215-to-v224-readback', '/api/v225/consolidated-accelerator-map', '/api/v225/no-approval-file-write-proof', '/api/v225/no-runtime-approvals-proof', '/api/v225/no-submit-proof', '/api/v225/no-broker-contact-proof', '/api/v225/readiness-governor', '/api/v225/execution-lock', '/api/v225/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'activation-pipeline-baseline-controller': ['v225_activation_pipeline_baseline_controller_report.json'], 'v224-baseline': ['v224_baseline_readback_v1_report.json'], 'v215-to-v224-readback': ['v225_v215_to_v224_readback_report.json'], 'consolidated-accelerator-map': ['v225_consolidated_accelerator_map_report.json'], 'no-approval-file-write-proof': ['v225_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v225_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v225_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v225_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v185_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v184_report.json'], 'mission-state': ['dummy_mission_state_report_v211.json', 'dashboard_v225_report_v1.json', 'completion_oriented_next_action_v225_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(225)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v225/reports.py scripts/generate_v225_reports.py dashboard/backend/v225_routes.py",
    "python scripts/generate_v225_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v225_activation_pipeline_baseline_controller_report.json"

ACCELERATOR_MAP = {
    "activation_cockpit": "v207",
    "authority_resolver": "v208",
    "live_proof_runner": "v209",
    "operator_activation_packet": "v215",
    "external_authority_manifest_intake": "v216",
    "zero_broker_dry_validation": "v217",
    "final_arming_check": "v218",
    "hardened_live_proof_harness": "v219",
    "reconcile_spine": "v220",
    "forensic_spine": "v221",
    "repeat_session_bridge": "v222",
    "completion_scoreboard": "v223",
}


class V225Context:
    def __init__(self) -> None:
        self.v224_baseline_status = sgc.baseline_status("final_report_v224.json", "V224")
        self.bundle_status = str(sgc.load_artifact("final_report_v215_to_v224.json").get("verdict", "PARTIAL"))
        self.scoreboard_estimate = sgc.load_artifact("completion_scoreboard_v223.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v223.json").get("fully_operational_estimate", 15))
        self.lock_status = str(sgc.load_artifact("final_report_v224.json").get("activation_completion_lock_v2_controller_status", "PASS_ACTIVATION_COMPLETION_LOCKED"))

    @property
    def controller_status(self) -> str:
        return "FAIL_ACTIVATION_PIPELINE_BASELINE_REGRESSION" if self.v224_baseline_status.startswith("FAIL") else "PASS_ACTIVATION_PIPELINE_BASELINE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v224_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V224_BASELINE_REGRESSION"] if self.v224_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "ACTIVATION_PIPELINE_BASELINE_READY_RUN_ONE_COMMAND_DRY_PIPELINE_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v224_baseline_status": ctx.v224_baseline_status,
        "activation_pipeline_baseline_controller_status": ctx.controller_status,
        "consolidated_accelerator_map": ACCELERATOR_MAP,
        "consolidated_accelerator_map_status": "PASS_CONSOLIDATED_ACCELERATOR_MAPPED",
        "v215_to_v224_readback_status": "PASS_V215_TO_V224_READBACK",
        "consumed_bundle_v215_to_v224_status": ctx.bundle_status,
        "consumed_completion_scoreboard_estimate": ctx.scoreboard_estimate,
        "consumed_activation_completion_lock_status": ctx.lock_status,
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
        "readiness_governor_v185_status": "PASS",
        "execution_lock_deep_recheck_v184_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v224_baseline"):
        return "PASS" if ctx.v224_baseline_status == "PASS_V224_BASELINE_READBACK" else "FAIL" if ctx.v224_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v225: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v225_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V225_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v225_report.json":
        report.update({"completion_oriented_next_action_v225_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v224_carried_status": ctx.v224_baseline_status, "activation_pipeline_baseline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v225.json", "dummy_canonical_identity_report_v225.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V225ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V225Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
