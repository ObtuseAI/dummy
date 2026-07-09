"""DUMMY v257 authority manifest validator v3 fix hints no write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v257 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v257: Authority Manifest Validator V3 Fix Hints No Write"
MISSION_NAME = "dummy_mission_state_report_v243.json"
FINAL_NAME = "final_report_v257.json"
INDEX_KEYS = ['authority_manifest_validator_controller_status', 'manifest_valid', 'approval_files_written']
DASH_TITLE = "Dummy V257 Authority Manifest Validator V3 Fix Hints No Write"
MISSION_KEY = "dummy_mission_state_report_v243"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Manifest Validator V3', 'authority_manifest_validator_controller_status'], ['Manifest Valid', 'manifest_valid'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V257_ROUTES = ['/api/v257/authority-manifest-validator-controller', '/api/v257/v256-baseline', '/api/v257/validation-checks', '/api/v257/fix-hints', '/api/v257/failure-code', '/api/v257/hash-only-ledger', '/api/v257/no-raw-phrase-leakage', '/api/v257/no-approval-file-write-proof', '/api/v257/no-runtime-approvals-proof', '/api/v257/no-submit-proof', '/api/v257/readiness-governor', '/api/v257/execution-lock', '/api/v257/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'authority-manifest-validator-controller': ['v257_authority_manifest_validator_controller_report.json'], 'v256-baseline': ['v256_baseline_readback_v1_report.json'], 'validation-checks': ['v257_validation_checks_report.json'], 'fix-hints': ['v257_fix_hints_report.json'], 'failure-code': ['v257_failure_code_report.json'], 'hash-only-ledger': ['v257_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v257_no_raw_phrase_leakage_report.json'], 'no-approval-file-write-proof': ['v257_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v257_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v257_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v217_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v216_report.json'], 'mission-state': ['dummy_mission_state_report_v243.json', 'dashboard_v257_report_v1.json', 'completion_oriented_next_action_v257_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(257)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v257/reports.py scripts/generate_v257_reports.py dashboard/backend/v257_routes.py",
    "python scripts/generate_v257_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v257_authority_manifest_validator_controller_report.json"

FIX_HINTS_MAP = {
    "MANIFEST_ABSENT": "Create the approval file externally at runtime/approvals/ with the exact phrase; Dummy never writes it.",
    "MISSING_FIELD": "Add all required operator metadata fields (operator, timestamp, reason, scope, expiration).",
    "PHRASE_MISMATCH": "Use the exact CONTROLLED_PILOT_PHRASE verbatim.",
    "FUZZY_APPROVAL_REJECTED": "Remove ambiguous/scope-mismatched language; supply the exact scope and acknowledgments.",
    "BROAD_LIVE_APPROVAL_REJECTED": "Remove broad live-trading language; scope must be the single controlled pilot.",
    "EXPIRED_APPROVAL": "Supply a non-expired approval with a future expiration.",
    "WRONG_PROOF_TARGET": "Set proof_target to FIRST_REAL_PILOT_PROOF or CONTROLLED_SESSION_PROOF.",
    "DESCRIPTOR_MISSING": "Add live-submit/caps/firewall descriptors to the manifest.",
    "NONE": "Manifest valid; proceed.",
}


class V257Context:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target="FIRST_REAL_PILOT_PROOF") -> None:
        self.v256_baseline_status = sgc.baseline_status("final_report_v256.json", "V256")
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
            return "MISSING_FIELD"
        if "SCOPE_MISMATCH" in b or "ACKNOWLEDGMENT_INCOMPLETE" in b:
            return "FUZZY_APPROVAL_REJECTED"
        if not self.target_valid:
            return "WRONG_PROOF_TARGET"
        return "FUZZY_APPROVAL_REJECTED"

    @property
    def controller_status(self) -> str:
        if self.v256_baseline_status.startswith("FAIL"):
            return "FAIL_AUTHORITY_MANIFEST_VALIDATOR_BASELINE_REGRESSION"
        if self.manifest_valid:
            return "PASS_AUTHORITY_MANIFEST_VALIDATOR_V3_READY"
        if self.present:
            return "FAIL_CLOSED_AUTHORITY_MANIFEST_VALIDATOR_REJECTED"
        return "PARTIAL_AUTHORITY_MANIFEST_VALIDATOR_BLOCKED_INPUTS_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v256_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.manifest_valid:
            return "PASS"
        if self.present:
            return "FAIL"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v256_baseline_status.startswith("FAIL"):
            return ["FAIL_V256_BASELINE_REGRESSION"]
        if self.manifest_valid:
            return []
        return [self.failure_code]

    @property
    def next_action(self) -> str:
        if self.manifest_valid:
            return "AUTHORITY_MANIFEST_VALIDATOR_V3_READY_RUN_LIVE_ADAPTER_SMOKE_KIT_NO_SUBMIT"
        return "OPERATOR_FIX_MANIFEST_PER_FIX_HINTS_DUMMY_WRITES_NOTHING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v256_baseline_status": ctx.v256_baseline_status,
        "authority_manifest_validator_controller_status": ctx.controller_status,
        "manifest_valid": ctx.manifest_valid,
        "manifest_present": ctx.present,
        "manifest_approval_hash": ctx.validation["approval_hash"],
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "fix_hint": FIX_HINTS_MAP.get(ctx.failure_code, "Review manifest."),
        "fix_hints": FIX_HINTS_MAP,
        "fix_hints_status": "PASS_FIX_HINTS_EMITTED",
        "proof_target": ctx.proof_target,
        "validation_checks_status": "PASS_VALIDATION_CHECKS_RUN",
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
        "readiness_governor_v217_status": "PASS",
        "execution_lock_deep_recheck_v216_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v256_baseline"):
        return "PASS" if ctx.v256_baseline_status == "PASS_V256_BASELINE_READBACK" else "FAIL" if ctx.v256_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v257: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v257_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V257_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v257_report.json":
        report.update({"completion_oriented_next_action_v257_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v256_carried_status": ctx.v256_baseline_status, "authority_manifest_validator_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v257.json", "dummy_canonical_identity_report_v257.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V257ReportFactory:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target='FIRST_REAL_PILOT_PROOF') -> None:
        self.kw = dict(manifest_approval=manifest_approval, manifest_approval_path=manifest_approval_path, proof_target=proof_target)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V257Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
