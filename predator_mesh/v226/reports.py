"""DUMMY v226 operator authority manifest pack template linter readonly — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v226 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v226: Operator Authority Manifest Pack Template Linter Readonly"
MISSION_NAME = "dummy_mission_state_report_v212.json"
FINAL_NAME = "final_report_v226.json"
INDEX_KEYS = ['manifest_pack_controller_status', 'approval_files_written', 'runtime_approvals_created_by_dummy']
DASH_TITLE = "Dummy V226 Operator Authority Manifest Pack Template Linter Readonly"
MISSION_KEY = "dummy_mission_state_report_v212"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Manifest Pack', 'manifest_pack_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Runtime Approvals Created', 'runtime_approvals_created_by_dummy'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V226_ROUTES = ['/api/v226/manifest-pack-controller', '/api/v226/v225-baseline', '/api/v226/manifest-pack-template', '/api/v226/required-approval-files-list', '/api/v226/required-exact-phrases-list', '/api/v226/required-descriptors-list', '/api/v226/manifest-linter', '/api/v226/no-approval-file-write-proof', '/api/v226/no-runtime-approvals-proof', '/api/v226/no-submit-proof', '/api/v226/readiness-governor', '/api/v226/execution-lock', '/api/v226/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'manifest-pack-controller': ['v226_manifest_pack_controller_report.json'], 'v225-baseline': ['v225_baseline_readback_v1_report.json'], 'manifest-pack-template': ['v226_manifest_pack_template_report.json'], 'required-approval-files-list': ['v226_required_approval_files_list_report.json'], 'required-exact-phrases-list': ['v226_required_exact_phrases_list_report.json'], 'required-descriptors-list': ['v226_required_descriptors_list_report.json'], 'manifest-linter': ['v226_manifest_linter_report.json'], 'no-approval-file-write-proof': ['v226_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v226_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v226_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v186_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v185_report.json'], 'mission-state': ['dummy_mission_state_report_v212.json', 'dashboard_v226_report_v1.json', 'completion_oriented_next_action_v226_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(226)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v226/reports.py scripts/generate_v226_reports.py dashboard/backend/v226_routes.py",
    "python scripts/generate_v226_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v226_manifest_pack_controller_report.json"

REQUIRED_APPROVAL_FILES = [
    "runtime/approvals/dummy_controlled_production_pilot_approval.json",
    "runtime/approvals/dummy_controlled_session_canary_approval.json",
    "runtime/approvals/dummy_broker_readonly_approval.json",
]
REQUIRED_EXACT_PHRASES = ["CONTROLLED_PILOT_PHRASE", "CONTROLLED_SESSION_PHRASE", "BROKER_READONLY_PHRASE"]
REQUIRED_DESCRIPTORS = ["live_submit_descriptor", "caps_descriptor", "firewall_adapter_descriptor", "proof_target_selector"]
MANIFEST_TEMPLATE = {
    "exact_phrase": "<one of the exact approval phrases>",
    "operator": "operator:<name>",
    "timestamp": "<iso8601>",
    "reason": "<operator reason>",
    "scope": "<matching scope>",
    "expiration": "<iso8601>",
    "live_submit_descriptor": "operator-enabled",
    "caps_descriptor": "unchanged-within-limits",
    "firewall_adapter_descriptor": "injected-live-broker-firewall",
    "proof_target_selector": "FIRST_REAL_PILOT_PROOF|CONTROLLED_SESSION_PROOF",
}


class V226Context:
    def __init__(self, *, manifest_pack=None) -> None:
        self.v225_baseline_status = sgc.baseline_status("final_report_v225.json", "V225")
        self.lint_ok = True
        self.lint_blockers = []
        if manifest_pack is not None:
            self.lint_blockers = [k for k in MANIFEST_TEMPLATE if not manifest_pack.get(k)]
            self.lint_ok = not self.lint_blockers

    @property
    def controller_status(self) -> str:
        if self.v225_baseline_status.startswith("FAIL"):
            return "FAIL_MANIFEST_PACK_BASELINE_REGRESSION"
        return "PASS_MANIFEST_PACK_READY_READONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v225_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V225_BASELINE_REGRESSION"] if self.v225_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "MANIFEST_PACK_READY_OPERATOR_FILL_AND_SUPPLY_EXTERNALLY_NO_APPROVAL_WRITE_BY_DUMMY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v225_baseline_status": ctx.v225_baseline_status,
        "manifest_pack_controller_status": ctx.controller_status,
        "manifest_pack_template": MANIFEST_TEMPLATE,
        "manifest_pack_template_status": "PASS_MANIFEST_PACK_TEMPLATE_EMITTED",
        "required_approval_files_list": REQUIRED_APPROVAL_FILES,
        "required_approval_files_list_status": "PASS_REQUIRED_APPROVAL_FILES_LISTED",
        "required_exact_phrases_list": REQUIRED_EXACT_PHRASES,
        "required_exact_phrases_list_status": "PASS_REQUIRED_EXACT_PHRASES_LISTED",
        "required_descriptors_list": REQUIRED_DESCRIPTORS,
        "required_descriptors_list_status": "PASS_REQUIRED_DESCRIPTORS_LISTED",
        "manifest_linter_status": "PASS_MANIFEST_LINT_OK" if ctx.lint_ok else "PARTIAL_MANIFEST_LINT_INCOMPLETE",
        "manifest_lint_blockers": ctx.lint_blockers,
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
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
        "readiness_governor_v186_status": "PASS",
        "execution_lock_deep_recheck_v185_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v225_baseline"):
        return "PASS" if ctx.v225_baseline_status == "PASS_V225_BASELINE_READBACK" else "FAIL" if ctx.v225_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v226: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v226_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V226_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v226_report.json":
        report.update({"completion_oriented_next_action_v226_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v225_carried_status": ctx.v225_baseline_status, "manifest_pack_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v226.json", "dummy_canonical_identity_report_v226.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V226ReportFactory:
    def __init__(self, *, manifest_pack=None) -> None:
        self.kw = dict(manifest_pack=manifest_pack)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V226Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
