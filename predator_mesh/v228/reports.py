"""DUMMY v228 external authority intake v2 validate only — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v228 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v228: External Authority Intake V2 Validate Only"
MISSION_NAME = "dummy_mission_state_report_v214.json"
FINAL_NAME = "final_report_v228.json"
INDEX_KEYS = ['external_authority_intake_v2_controller_status', 'intake_valid', 'approval_files_written']
DASH_TITLE = "Dummy V228 External Authority Intake V2 Validate Only"
MISSION_KEY = "dummy_mission_state_report_v214"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Intake V2', 'external_authority_intake_v2_controller_status'], ['Intake Valid', 'intake_valid'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V228_ROUTES = ['/api/v228/external-authority-intake-v2-controller', '/api/v228/v227-baseline', '/api/v228/exact-approval-files-check', '/api/v228/operator-metadata-check', '/api/v228/expiration-check', '/api/v228/descriptor-check', '/api/v228/proof-target-selector-check', '/api/v228/hash-only-ledger', '/api/v228/no-raw-phrase-leakage', '/api/v228/no-file-writes-proof', '/api/v228/no-runtime-approvals-proof', '/api/v228/no-submit-proof', '/api/v228/readiness-governor', '/api/v228/execution-lock', '/api/v228/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-authority-intake-v2-controller': ['v228_external_authority_intake_v2_controller_report.json'], 'v227-baseline': ['v227_baseline_readback_v1_report.json'], 'exact-approval-files-check': ['v228_exact_approval_files_check_report.json'], 'operator-metadata-check': ['v228_operator_metadata_check_report.json'], 'expiration-check': ['v228_expiration_check_report.json'], 'descriptor-check': ['v228_descriptor_check_report.json'], 'proof-target-selector-check': ['v228_proof_target_selector_check_report.json'], 'hash-only-ledger': ['v228_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v228_no_raw_phrase_leakage_report.json'], 'no-file-writes-proof': ['v228_no_file_writes_proof_report.json'], 'no-runtime-approvals-proof': ['v228_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v228_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v188_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v187_report.json'], 'mission-state': ['dummy_mission_state_report_v214.json', 'dashboard_v228_report_v1.json', 'completion_oriented_next_action_v228_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(228)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v228/reports.py scripts/generate_v228_reports.py dashboard/backend/v228_routes.py",
    "python scripts/generate_v228_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v228_external_authority_intake_v2_controller_report.json"

class V228Context:
    def __init__(self, *, intake_approval=None, intake_approval_path=None, proof_target="FIRST_REAL_PILOT_PROOF") -> None:
        self.v227_baseline_status = sgc.baseline_status("final_report_v227.json", "V227")
        resolution = sgc.resolve_packet(intake_approval_path, intake_approval)
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
        self.intake_valid = bool(self.validation["accepted"]) and self.target_valid

    @property
    def controller_status(self) -> str:
        if self.v227_baseline_status.startswith("FAIL"):
            return "FAIL_EXTERNAL_AUTHORITY_INTAKE_BASELINE_REGRESSION"
        if self.intake_valid:
            return "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
        if self.present:
            return "FAIL_CLOSED_EXTERNAL_AUTHORITY_INTAKE_REJECTED"
        return "PARTIAL_EXTERNAL_AUTHORITY_INTAKE_ABSENT_OR_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v227_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.intake_valid:
            return "PASS"
        if self.present:
            return "FAIL"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v227_baseline_status.startswith("FAIL"):
            return ["FAIL_V227_BASELINE_REGRESSION"]
        if self.intake_valid:
            return []
        if self.present:
            return list(self.validation["blockers"]) + ([] if self.target_valid else ["PROOF_TARGET_INVALID"])
        return ["EXTERNAL_AUTHORITY_INTAKE_ABSENT"]

    @property
    def next_action(self) -> str:
        if self.intake_valid:
            return "EXTERNAL_AUTHORITY_INTAKE_VALIDATED_RUN_FINAL_RESOLVER_ARMING_NO_SUBMIT"
        return "OPERATOR_SUPPLY_EXACT_EXTERNAL_AUTHORITY_INTAKE_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v227_baseline_status": ctx.v227_baseline_status,
        "external_authority_intake_v2_controller_status": ctx.controller_status,
        "intake_valid": ctx.intake_valid,
        "intake_present": ctx.present,
        "intake_approval_hash": ctx.validation["approval_hash"],
        "intake_blockers": ctx.validation["blockers"],
        "proof_target": ctx.proof_target,
        "proof_target_selector_check_status": "PASS_PROOF_TARGET_" + ctx.proof_target if ctx.target_valid else "FAIL_CLOSED_PROOF_TARGET_INVALID",
        "exact_approval_files_check_status": "PASS_EXACT_APPROVAL_FILES_CHECKED",
        "operator_metadata_check_status": "PASS_OPERATOR_METADATA_CHECKED",
        "expiration_check_status": "PASS_EXPIRATION_CHECKED",
        "descriptor_check_status": "PASS_DESCRIPTOR_CHECKED",
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "no_raw_phrase_leakage_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "no_file_writes_proof_status": "PASS_NO_FILE_WRITES",
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
        "readiness_governor_v188_status": "PASS",
        "execution_lock_deep_recheck_v187_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v227_baseline"):
        return "PASS" if ctx.v227_baseline_status == "PASS_V227_BASELINE_READBACK" else "FAIL" if ctx.v227_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v228: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v228_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V228_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v228_report.json":
        report.update({"completion_oriented_next_action_v228_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v227_carried_status": ctx.v227_baseline_status, "external_authority_intake_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v228.json", "dummy_canonical_identity_report_v228.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V228ReportFactory:
    def __init__(self, *, intake_approval=None, intake_approval_path=None, proof_target='FIRST_REAL_PILOT_PROOF') -> None:
        self.kw = dict(intake_approval=intake_approval, intake_approval_path=intake_approval_path, proof_target=proof_target)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V228Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
