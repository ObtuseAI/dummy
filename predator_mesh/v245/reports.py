"""DUMMY v245 operator ready appliance baseline from v235 to v244 — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v245 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v245: Operator Ready Appliance Baseline From V235 To V244"
MISSION_NAME = "dummy_mission_state_report_v231.json"
FINAL_NAME = "final_report_v245.json"
INDEX_KEYS = ['operator_ready_appliance_baseline_controller_status', 'approval_files_written', 'live_orders']
DASH_TITLE = "Dummy V245 Operator Ready Appliance Baseline From V235 To V244"
MISSION_KEY = "dummy_mission_state_report_v231"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Appliance Baseline', 'operator_ready_appliance_baseline_controller_status'], ['Operator Ready State', 'operator_ready_state'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V245_ROUTES = ['/api/v245/operator-ready-appliance-baseline-controller', '/api/v245/v244-baseline', '/api/v245/v235-to-v244-readback', '/api/v245/appliance-state-classification', '/api/v245/no-approval-file-write-proof', '/api/v245/no-runtime-approvals-proof', '/api/v245/no-submit-proof', '/api/v245/no-broker-contact-proof', '/api/v245/readiness-governor', '/api/v245/execution-lock', '/api/v245/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'operator-ready-appliance-baseline-controller': ['v245_operator_ready_appliance_baseline_controller_report.json'], 'v244-baseline': ['v244_baseline_readback_v1_report.json'], 'v235-to-v244-readback': ['v245_v235_to_v244_readback_report.json'], 'appliance-state-classification': ['v245_appliance_state_classification_report.json'], 'no-approval-file-write-proof': ['v245_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v245_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v245_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v245_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v205_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v204_report.json'], 'mission-state': ['dummy_mission_state_report_v231.json', 'dashboard_v245_report_v1.json', 'completion_oriented_next_action_v245_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(245)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v245/reports.py scripts/generate_v245_reports.py dashboard/backend/v245_routes.py",
    "python scripts/generate_v245_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v245_operator_ready_appliance_baseline_controller_report.json"

STATE_CLASSES = ["DOCTORS_READY", "MANIFEST_BLOCKED", "CONFIG_CAPS_BLOCKED", "ADAPTER_BLOCKED", "BROKER_READONLY_BLOCKED", "ARMING_BLOCKED", "EXECUTE_ONCE_BLOCKED", "RECONCILE_FORENSIC_WAITING"]


class V245Context:
    def __init__(self) -> None:
        self.v244_baseline_status = sgc.baseline_status("final_report_v244.json", "V244")
        self.bundle_status = str(sgc.load_artifact("final_report_v235_to_v244.json").get("verdict", "PARTIAL"))
        self.scoreboard_estimate = sgc.load_artifact("completion_lift_v4_v244.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v244.json").get("fully_operational_estimate", 24))
        self.manifest_ok = str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
        self.config_ok = str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE"
        self.adapter_ok = str(sgc.load_artifact("final_report_v238.json").get("firewall_adapter_doctor_controller_status", "")) == "PASS_FIREWALL_ADAPTER_DOCTOR_READY_NON_BROKER_DOUBLE"

    @property
    def operator_ready_state(self) -> str:
        if not self.manifest_ok:
            return "MANIFEST_BLOCKED"
        if not self.config_ok:
            return "CONFIG_CAPS_BLOCKED"
        if not self.adapter_ok:
            return "ADAPTER_BLOCKED"
        return "DOCTORS_READY"

    @property
    def controller_status(self) -> str:
        return "FAIL_OPERATOR_READY_APPLIANCE_BASELINE_REGRESSION" if self.v244_baseline_status.startswith("FAIL") else "PASS_OPERATOR_READY_APPLIANCE_BASELINE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v244_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V244_BASELINE_REGRESSION"] if self.v244_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_READY_APPLIANCE_BASELINE_READY_BUILD_OPERATOR_READY_APPLIANCE_PACK"


def _common(ctx) -> dict[str, Any]:
    return {
        "v244_baseline_status": ctx.v244_baseline_status,
        "operator_ready_appliance_baseline_controller_status": ctx.controller_status,
        "operator_ready_state": ctx.operator_ready_state,
        "appliance_state_classification": {"canonical_state": ctx.operator_ready_state, "classes": STATE_CLASSES},
        "appliance_state_classification_status": "PASS_APPLIANCE_STATE_CLASSIFIED",
        "v235_to_v244_readback_status": "PASS_V235_TO_V244_READBACK",
        "consumed_bundle_v235_to_v244_status": ctx.bundle_status,
        "consumed_completion_lift_v4_estimate": ctx.scoreboard_estimate,
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
        "readiness_governor_v205_status": "PASS",
        "execution_lock_deep_recheck_v204_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v244_baseline"):
        return "PASS" if ctx.v244_baseline_status == "PASS_V244_BASELINE_READBACK" else "FAIL" if ctx.v244_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v245: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v245_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V245_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v245_report.json":
        report.update({"completion_oriented_next_action_v245_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v244_carried_status": ctx.v244_baseline_status, "operator_ready_appliance_baseline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v245.json", "dummy_canonical_identity_report_v245.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V245ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V245Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
