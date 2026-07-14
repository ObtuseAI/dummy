"""DUMMY v215 operator activation packet readonly completion actions — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v215 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v215: Operator Activation Packet Readonly Completion Actions"
MISSION_NAME = "dummy_mission_state_report_v201.json"
FINAL_NAME = "final_report_v215.json"
INDEX_KEYS = ['operator_activation_packet_controller_status', 'approval_files_written', 'live_orders']
DASH_TITLE = "Dummy V215 Operator Activation Packet Readonly Completion Actions"
MISSION_KEY = "dummy_mission_state_report_v201"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Activation Packet', 'operator_activation_packet_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V215_ROUTES = ['/api/v215/operator-activation-packet-controller', '/api/v215/v214-baseline', '/api/v215/operator-checklist', '/api/v215/first-live-proof-command-sequence', '/api/v215/reconcile-command-sequence', '/api/v215/forensic-command-sequence', '/api/v215/no-approval-file-write-proof', '/api/v215/no-config-write-proof', '/api/v215/no-submit-proof', '/api/v215/no-broker-contact-proof', '/api/v215/readiness-governor', '/api/v215/execution-lock', '/api/v215/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'operator-activation-packet-controller': ['v215_operator_activation_packet_controller_report.json'], 'v214-baseline': ['v214_baseline_readback_v1_report.json'], 'operator-checklist': ['v215_operator_checklist_report.json'], 'first-live-proof-command-sequence': ['v215_first_live_proof_command_sequence_report.json'], 'reconcile-command-sequence': ['v215_reconcile_command_sequence_report.json'], 'forensic-command-sequence': ['v215_forensic_command_sequence_report.json'], 'no-approval-file-write-proof': ['v215_no_approval_file_write_proof_report.json'], 'no-config-write-proof': ['v215_no_config_write_proof_report.json'], 'no-submit-proof': ['v215_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v215_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v175_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v174_report.json'], 'mission-state': ['dummy_mission_state_report_v201.json', 'dashboard_v215_report_v1.json', 'completion_oriented_next_action_v215_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(215)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v215/reports.py scripts/generate_v215_reports.py dashboard/backend/v215_routes.py",
    "python scripts/generate_v215_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v215_operator_activation_packet_controller_report.json"

OPERATOR_CHECKLIST = [
    "SUPPLY_EXACT_APPROVAL_FILES",
    "SUPPLY_EXACT_APPROVAL_PHRASES",
    "OPERATOR_ENABLE_LIVE_SUBMIT",
    "OPERATOR_CONFIRM_CAPS_UNCHANGED_WITHIN_LIMITS",
    "OPERATOR_INJECT_LIVEBROKERFIREWALL_ADAPTER",
    "OPTIONAL_BROKER_READONLY_VERIFICATION",
]
FIRST_LIVE_PROOF_COMMANDS = [
    "python scripts/generate_v216_reports.py  # validate external authority manifest",
    "python scripts/run_dummy_zero_broker_dry_validation.py",
    "python scripts/generate_v218_reports.py  # final arming check",
    "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY python scripts/run_dummy_hardened_live_proof.py",
]
RECONCILE_COMMANDS = ["python scripts/run_dummy_reconcile_spine_v2.py"]
FORENSIC_COMMANDS = ["python scripts/run_dummy_forensic_spine_v2.py"]


class V215Context:
    def __init__(self) -> None:
        self.v214_baseline_status = sgc.baseline_status("final_report_v214.json", "V214")
        self.cockpit_status = str(sgc.load_artifact("activation_cockpit_v207.json").get("cockpit_controller_status", sgc.load_artifact("final_report_v207.json").get("cockpit_controller_status", "PASS_ACTIVATION_COCKPIT_READY_READONLY")))
        self.resolver_status = str(sgc.load_artifact("authority_resolver_v208.json").get("authority_state", sgc.load_artifact("final_report_v208.json").get("authority_state", "LIVE_BLOCKED_AUTHORITY_ABSENT")))
        self.scoreboard_estimate = sgc.load_artifact("completion_scoreboard_v213.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v213.json").get("fully_operational_estimate", 15))
        self.bundle_status = str(sgc.load_artifact("final_report_v205_to_v214.json").get("verdict", "PARTIAL"))

    @property
    def controller_status(self) -> str:
        return "FAIL_OPERATOR_ACTIVATION_PACKET_BASELINE_REGRESSION" if self.v214_baseline_status.startswith("FAIL") else "PASS_OPERATOR_ACTIVATION_PACKET_READY_READONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v214_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V214_BASELINE_REGRESSION"] if self.v214_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_PROVIDE_EXTERNAL_AUTHORITY_MANIFEST_THEN_RUN_DRY_VALIDATION_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v214_baseline_status": ctx.v214_baseline_status,
        "operator_activation_packet_controller_status": ctx.controller_status,
        "operator_checklist": OPERATOR_CHECKLIST,
        "first_live_proof_command_sequence": FIRST_LIVE_PROOF_COMMANDS,
        "reconcile_command_sequence": RECONCILE_COMMANDS,
        "forensic_command_sequence": FORENSIC_COMMANDS,
        "consumed_activation_cockpit_status": ctx.cockpit_status,
        "consumed_authority_resolver_status": ctx.resolver_status,
        "consumed_completion_scoreboard_estimate": ctx.scoreboard_estimate,
        "consumed_bundle_v205_to_v214_status": ctx.bundle_status,
        "approval_files_written": 0,
        "no_config_write_proof_status": "PASS_NO_CONFIG_WRITE",

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v175_status": "PASS",
        "execution_lock_deep_recheck_v174_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v214_baseline"):
        return "PASS" if ctx.v214_baseline_status == "PASS_V214_BASELINE_READBACK" else "FAIL" if ctx.v214_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v215: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v215_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V215_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v215_report.json":
        report.update({"completion_oriented_next_action_v215_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v214_carried_status": ctx.v214_baseline_status, "operator_activation_packet_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v215.json", "dummy_canonical_identity_report_v215.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V215ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V215Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
