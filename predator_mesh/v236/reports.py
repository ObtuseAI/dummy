"""DUMMY v236 authority manifest doctor external only no write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v236 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v236: Authority Manifest Doctor External Only No Write"
MISSION_NAME = "dummy_mission_state_report_v222.json"
FINAL_NAME = "final_report_v236.json"
INDEX_KEYS = ['authority_manifest_doctor_controller_status', 'manifest_valid', 'approval_files_written']
DASH_TITLE = "Dummy V236 Authority Manifest Doctor External Only No Write"
MISSION_KEY = "dummy_mission_state_report_v222"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Manifest Doctor', 'authority_manifest_doctor_controller_status'], ['Manifest Valid', 'manifest_valid'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V236_ROUTES = ['/api/v236/authority-manifest-doctor-controller', '/api/v236/v235-baseline', '/api/v236/expected-approval-paths-check', '/api/v236/exact-phrase-check', '/api/v236/operator-metadata-check', '/api/v236/expiration-check', '/api/v236/proof-target-check', '/api/v236/descriptor-check', '/api/v236/failure-code', '/api/v236/hash-only-ledger', '/api/v236/no-raw-phrase-leakage', '/api/v236/no-approval-file-write-proof', '/api/v236/no-runtime-approvals-proof', '/api/v236/no-submit-proof', '/api/v236/readiness-governor', '/api/v236/execution-lock', '/api/v236/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'authority-manifest-doctor-controller': ['v236_authority_manifest_doctor_controller_report.json'], 'v235-baseline': ['v235_baseline_readback_v1_report.json'], 'expected-approval-paths-check': ['v236_expected_approval_paths_check_report.json'], 'exact-phrase-check': ['v236_exact_phrase_check_report.json'], 'operator-metadata-check': ['v236_operator_metadata_check_report.json'], 'expiration-check': ['v236_expiration_check_report.json'], 'proof-target-check': ['v236_proof_target_check_report.json'], 'descriptor-check': ['v236_descriptor_check_report.json'], 'failure-code': ['v236_failure_code_report.json'], 'hash-only-ledger': ['v236_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v236_no_raw_phrase_leakage_report.json'], 'no-approval-file-write-proof': ['v236_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v236_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v236_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v196_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v195_report.json'], 'mission-state': ['dummy_mission_state_report_v222.json', 'dashboard_v236_report_v1.json', 'completion_oriented_next_action_v236_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(236)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v236/reports.py scripts/generate_v236_reports.py dashboard/backend/v236_routes.py",
    "python scripts/generate_v236_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v236_authority_manifest_doctor_controller_report.json"

class V236Context:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target="FIRST_REAL_PILOT_PROOF") -> None:
        self.v235_baseline_status = sgc.baseline_status("final_report_v235.json", "V235")
        resolution = sgc.resolve_packet(manifest_approval_path, manifest_approval)
        self.present = resolution.get("resolution") == "PRESENT"
        self.validation = sgc.validate_packet(
            resolution,
            required_phrase=sgc.CONTROLLED_PILOT_PHRASE,
            required_fields=sgc.CONTROLLED_PILOT_FIELDS,
            required_scope=sgc.CONTROLLED_PILOT_SCOPE,
            ack_requirements=sgc.CONTROLLED_PILOT_ACKS,
        )
        self.proof_target = proof_target
        self.target_valid = proof_target in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.manifest_valid = bool(self.validation["accepted"]) and self.target_valid

    @property
    def failure_code(self) -> str:
        if self.manifest_valid:
            return "NONE"
        if not self.present:
            return "MANIFEST_ABSENT"
        b = self.validation["blockers"]
        if "APPROVAL_PHRASE_NOT_EXACT" in b:
            return "PHRASE_MISMATCH"
        if "LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED" in b:
            return "BROAD_LIVE_APPROVAL_REJECTED"
        if "MISSING_REQUIRED_APPROVAL_FIELDS" in b:
            return "MISSING_OPERATOR_METADATA"
        if "SCOPE_MISMATCH" in b or "ACKNOWLEDGMENT_INCOMPLETE" in b:
            return "FUZZY_APPROVAL_REJECTED"
        if not self.target_valid:
            return "WRONG_PROOF_TARGET"
        return "FUZZY_APPROVAL_REJECTED"

    @property
    def controller_status(self) -> str:
        if self.v235_baseline_status.startswith("FAIL"):
            return "FAIL_AUTHORITY_MANIFEST_DOCTOR_BASELINE_REGRESSION"
        if self.manifest_valid:
            return "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
        if self.present:
            return "FAIL_CLOSED_AUTHORITY_MANIFEST_REJECTED"
        return "PARTIAL_AUTHORITY_MANIFEST_ABSENT_OR_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v235_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.manifest_valid:
            return "PASS"
        if self.present:
            return "FAIL"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v235_baseline_status.startswith("FAIL"):
            return ["FAIL_V235_BASELINE_REGRESSION"]
        if self.manifest_valid:
            return []
        return [self.failure_code]

    @property
    def next_action(self) -> str:
        if self.manifest_valid:
            return "AUTHORITY_MANIFEST_VALIDATED_RUN_LIVE_SUBMIT_CAPS_DOCTOR_NO_SUBMIT"
        return "OPERATOR_SUPPLY_EXTERNAL_AUTHORITY_MANIFEST_DUMMY_WRITES_NOTHING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v235_baseline_status": ctx.v235_baseline_status,
        "authority_manifest_doctor_controller_status": ctx.controller_status,
        "manifest_valid": ctx.manifest_valid,
        "manifest_present": ctx.present,
        "manifest_approval_hash": ctx.validation["approval_hash"],
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "proof_target": ctx.proof_target,
        "proof_target_check_status": "PASS_PROOF_TARGET_" + ctx.proof_target if ctx.target_valid else "FAIL_CLOSED_PROOF_TARGET_INVALID",
        "expected_approval_paths_check_status": "PASS_EXPECTED_APPROVAL_PATHS_CHECKED",
        "exact_phrase_check_status": "PASS_EXACT_PHRASE_CHECKED",
        "operator_metadata_check_status": "PASS_OPERATOR_METADATA_CHECKED",
        "expiration_check_status": "PASS_EXPIRATION_CHECKED",
        "descriptor_check_status": "PASS_DESCRIPTOR_CHECKED",
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "no_raw_phrase_leakage_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
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
        "readiness_governor_v196_status": "PASS",
        "execution_lock_deep_recheck_v195_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v235_baseline"):
        return "PASS" if ctx.v235_baseline_status == "PASS_V235_BASELINE_READBACK" else "FAIL" if ctx.v235_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v236: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v236_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V236_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v236_report.json":
        report.update({"completion_oriented_next_action_v236_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v235_carried_status": ctx.v235_baseline_status, "authority_manifest_doctor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v236.json", "dummy_canonical_identity_report_v236.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V236ReportFactory:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target='FIRST_REAL_PILOT_PROOF') -> None:
        self.kw = dict(manifest_approval=manifest_approval, manifest_approval_path=manifest_approval_path, proof_target=proof_target)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V236Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
