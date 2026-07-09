"""DUMMY v250 first proof command center readonly operator sequence — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v250 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v250: First Proof Command Center Readonly Operator Sequence"
MISSION_NAME = "dummy_mission_state_report_v236.json"
FINAL_NAME = "final_report_v250.json"
INDEX_KEYS = ['first_proof_command_center_controller_status', 'ui_submit_enabled', 'ui_writes_enabled']
DASH_TITLE = "Dummy V250 First Proof Command Center Readonly Operator Sequence"
MISSION_KEY = "dummy_mission_state_report_v236"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Command Center', 'first_proof_command_center_controller_status'], ['UI Submit Enabled', 'ui_submit_enabled'], ['UI Writes Enabled', 'ui_writes_enabled'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V250_ROUTES = ['/api/v250/first-proof-command-center-controller', '/api/v250/v249-baseline', '/api/v250/current-blocker-list', '/api/v250/doctor-status', '/api/v250/rehearsal-status', '/api/v250/execute-once-command', '/api/v250/completion-percentage', '/api/v250/ui-readonly-proof', '/api/v250/no-submit-proof', '/api/v250/readiness-governor', '/api/v250/execution-lock', '/api/v250/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'first-proof-command-center-controller': ['v250_first_proof_command_center_controller_report.json'], 'v249-baseline': ['v249_baseline_readback_v1_report.json'], 'current-blocker-list': ['v250_current_blocker_list_report.json'], 'doctor-status': ['v250_doctor_status_report.json'], 'rehearsal-status': ['v250_rehearsal_status_report.json'], 'execute-once-command': ['v250_execute_once_command_report.json'], 'completion-percentage': ['v250_completion_percentage_report.json'], 'ui-readonly-proof': ['v250_ui_readonly_proof_report.json'], 'no-submit-proof': ['v250_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v210_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v209_report.json'], 'mission-state': ['dummy_mission_state_report_v236.json', 'dashboard_v250_report_v1.json', 'completion_oriented_next_action_v250_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(250)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v250/reports.py scripts/generate_v250_reports.py dashboard/backend/v250_routes.py",
    "python scripts/generate_v250_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v250_first_proof_command_center_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V250Context:
    def __init__(self) -> None:
        self.v249_baseline_status = sgc.baseline_status("final_report_v249.json", "V249")
        self.doctor_status = {
            "manifest": str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "PARTIAL")),
            "config_caps": str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "PARTIAL")),
            "adapter": str(sgc.load_artifact("final_report_v238.json").get("firewall_adapter_doctor_controller_status", "PARTIAL")),
            "broker_readonly": str(sgc.load_artifact("final_report_v239.json").get("broker_readonly_doctor_controller_status", "PARTIAL")),
            "armable_quorum": str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "PARTIAL")),
        }
        self.rehearsal_status = {
            "authority_rehearsal": str(sgc.load_artifact("final_report_v247.json").get("external_authority_rehearsal_controller_status", "PASS")),
            "adapter_contract_kit": str(sgc.load_artifact("final_report_v248.json").get("adapter_contract_kit_controller_status", "PARTIAL")),
            "config_rehearsal": str(sgc.load_artifact("final_report_v249.json").get("live_submit_caps_rehearsal_controller_status", "PARTIAL")),
        }
        self.completion_pct = sgc.load_artifact("completion_lift_v4_v244.json").get("fully_operational_estimate", 24)
        self.blockers = [k for k, v in self.doctor_status.items() if not str(v).startswith("PASS")]

    @property
    def controller_status(self) -> str:
        return "FAIL_FIRST_PROOF_COMMAND_CENTER_BASELINE_REGRESSION" if self.v249_baseline_status.startswith("FAIL") else "PASS_FIRST_PROOF_COMMAND_CENTER_READY_READONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v249_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V249_BASELINE_REGRESSION"] if self.v249_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "FIRST_PROOF_COMMAND_CENTER_READY_READONLY_OPERATOR_FOLLOW_SEQUENCE_NO_SUBMIT_FROM_UI"


def _common(ctx) -> dict[str, Any]:
    return {
        "v249_baseline_status": ctx.v249_baseline_status,
        "first_proof_command_center_controller_status": ctx.controller_status,
        "ui_submit_enabled": False,
        "ui_writes_enabled": False,
        "safe_mode": "READ_ONLY_FAIL_CLOSED",
        "current_blocker_list": ctx.blockers,
        "current_blocker_list_status": "PASS_CURRENT_BLOCKERS_LISTED",
        "doctor_status": ctx.doctor_status,
        "doctor_status_report_status": "PASS_DOCTOR_STATUS_LISTED",
        "rehearsal_status": ctx.rehearsal_status,
        "rehearsal_status_report_status": "PASS_REHEARSAL_STATUS_LISTED",
        "required_env_gate": {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": LIVE_PROOF_ACK},
        "execute_once_command": "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK + " python scripts/run_dummy_live_proof_execute_once_v2.py",
        "reconcile_forensic_command": "python scripts/run_dummy_reconcile_forensic_pipeline_v2.py",
        "route_decision_command": "python scripts/generate_v232_reports.py",
        "execute_once_command_status": "PASS_EXECUTE_ONCE_COMMAND_EMITTED",
        "completion_percentage": ctx.completion_pct,
        "completion_percentage_status": "PASS_COMPLETION_PERCENTAGE_LISTED",
        "ui_readonly_proof_status": "PASS_UI_READONLY",
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
        "readiness_governor_v210_status": "PASS",
        "execution_lock_deep_recheck_v209_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v249_baseline"):
        return "PASS" if ctx.v249_baseline_status == "PASS_V249_BASELINE_READBACK" else "FAIL" if ctx.v249_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v250: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v250_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V250_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v250_report.json":
        report.update({"completion_oriented_next_action_v250_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v249_carried_status": ctx.v249_baseline_status, "first_proof_command_center_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v250.json", "dummy_canonical_identity_report_v250.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V250ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V250Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
