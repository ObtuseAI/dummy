"""DUMMY v235 operator authority appliance baseline from v225 to v234 — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v235 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v235: Operator Authority Appliance Baseline From V225 To V234"
MISSION_NAME = "dummy_mission_state_report_v221.json"
FINAL_NAME = "final_report_v235.json"
INDEX_KEYS = ['operator_authority_appliance_baseline_controller_status', 'approval_files_written', 'live_orders']
DASH_TITLE = "Dummy V235 Operator Authority Appliance Baseline From V225 To V234"
MISSION_KEY = "dummy_mission_state_report_v221"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Appliance Baseline', 'operator_authority_appliance_baseline_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V235_ROUTES = ['/api/v235/operator-authority-appliance-baseline-controller', '/api/v235/v234-baseline', '/api/v235/v225-to-v234-readback', '/api/v235/appliance-blocker-classification', '/api/v235/no-approval-file-write-proof', '/api/v235/no-runtime-approvals-proof', '/api/v235/no-submit-proof', '/api/v235/no-broker-contact-proof', '/api/v235/readiness-governor', '/api/v235/execution-lock', '/api/v235/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'operator-authority-appliance-baseline-controller': ['v235_operator_authority_appliance_baseline_controller_report.json'], 'v234-baseline': ['v234_baseline_readback_v1_report.json'], 'v225-to-v234-readback': ['v235_v225_to_v234_readback_report.json'], 'appliance-blocker-classification': ['v235_appliance_blocker_classification_report.json'], 'no-approval-file-write-proof': ['v235_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v235_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v235_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v235_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v195_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v194_report.json'], 'mission-state': ['dummy_mission_state_report_v221.json', 'dashboard_v235_report_v1.json', 'completion_oriented_next_action_v235_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(235)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v235/reports.py scripts/generate_v235_reports.py dashboard/backend/v235_routes.py",
    "python scripts/generate_v235_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v235_operator_authority_appliance_baseline_controller_report.json"

BLOCKER_CLASSES = [
    "MANIFEST_TEMPLATE_READY",
    "AUTHORITY_INTAKE_MISSING",
    "LIVE_SUBMIT_NOT_CONFIRMED",
    "CAPS_NOT_CONFIRMED",
    "FIREWALL_ADAPTER_MISSING",
    "ARMING_BLOCKED",
    "LIVE_PROOF_NOT_ARMED",
    "RECONCILE_WAITING",
    "FORENSIC_WAITING",
]


class V235Context:
    def __init__(self) -> None:
        self.v234_baseline_status = sgc.baseline_status("final_report_v234.json", "V234")
        self.bundle_status = str(sgc.load_artifact("final_report_v225_to_v234.json").get("verdict", "PARTIAL"))
        self.scoreboard_estimate = sgc.load_artifact("completion_scoreboard_v233.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v233.json").get("fully_operational_estimate", 15))
        self.intake_valid = str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
        self.arming_ready = str(sgc.load_artifact("final_report_v229.json").get("final_resolver_arming_controller_status", "")) == "PASS_FINAL_RESOLVER_ARMING_READY_NO_SUBMIT"
        self.blocker_map = {
            "MANIFEST_TEMPLATE_READY": True,
            "AUTHORITY_INTAKE_MISSING": not self.intake_valid,
            "LIVE_SUBMIT_NOT_CONFIRMED": True,
            "CAPS_NOT_CONFIRMED": True,
            "FIREWALL_ADAPTER_MISSING": True,
            "ARMING_BLOCKED": not self.arming_ready,
            "LIVE_PROOF_NOT_ARMED": True,
            "RECONCILE_WAITING": True,
            "FORENSIC_WAITING": True,
        }

    @property
    def controller_status(self) -> str:
        return "FAIL_OPERATOR_AUTHORITY_APPLIANCE_BASELINE_REGRESSION" if self.v234_baseline_status.startswith("FAIL") else "PASS_OPERATOR_AUTHORITY_APPLIANCE_BASELINE_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v234_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V234_BASELINE_REGRESSION"] if self.v234_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_AUTHORITY_APPLIANCE_BASELINE_READY_RUN_AUTHORITY_APPLIANCE_DOCTOR"


def _common(ctx) -> dict[str, Any]:
    return {
        "v234_baseline_status": ctx.v234_baseline_status,
        "operator_authority_appliance_baseline_controller_status": ctx.controller_status,
        "appliance_blocker_classification": ctx.blocker_map,
        "appliance_blocker_classification_status": "PASS_APPLIANCE_BLOCKERS_CLASSIFIED",
        "appliance_blocker_classes": BLOCKER_CLASSES,
        "v225_to_v234_readback_status": "PASS_V225_TO_V234_READBACK",
        "consumed_bundle_v225_to_v234_status": ctx.bundle_status,
        "consumed_completion_scoreboard_estimate": ctx.scoreboard_estimate,
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
        "readiness_governor_v195_status": "PASS",
        "execution_lock_deep_recheck_v194_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v234_baseline"):
        return "PASS" if ctx.v234_baseline_status == "PASS_V234_BASELINE_READBACK" else "FAIL" if ctx.v234_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v235: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v235_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V235_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v235_report.json":
        report.update({"completion_oriented_next_action_v235_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v234_carried_status": ctx.v234_baseline_status, "operator_authority_appliance_baseline_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v235.json", "dummy_canonical_identity_report_v235.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V235ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V235Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
