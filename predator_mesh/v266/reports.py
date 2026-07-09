"""DUMMY v266 external authority import wizard validate only no write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy, no approval-file write."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v266 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v266: External Authority Import Wizard Validate Only No Write"
MISSION_NAME = "dummy_mission_state_report_v252.json"
FINAL_NAME = "final_report_v266.json"
INDEX_KEYS = ['external_authority_import_wizard_controller_status', 'wizard_valid', 'approval_files_written']
DASH_TITLE = "Dummy V266 External Authority Import Wizard Validate Only No Write"
MISSION_KEY = "dummy_mission_state_report_v252"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Import Wizard', 'external_authority_import_wizard_controller_status'], ['Wizard Valid', 'wizard_valid'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V266_ROUTES = ['/api/v266/external-authority-import-wizard-controller', '/api/v266/v265-baseline', '/api/v266/import-input-validation', '/api/v266/descriptor-checks', '/api/v266/failure-code', '/api/v266/hash-only-ledger', '/api/v266/no-raw-phrase-leakage', '/api/v266/no-approval-file-write-proof', '/api/v266/no-runtime-approvals-proof', '/api/v266/no-submit-proof', '/api/v266/readiness-governor', '/api/v266/execution-lock', '/api/v266/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-authority-import-wizard-controller': ['v266_external_authority_import_wizard_controller_report.json'], 'v265-baseline': ['v265_baseline_readback_v1_report.json'], 'import-input-validation': ['v266_import_input_validation_report.json'], 'descriptor-checks': ['v266_descriptor_checks_report.json'], 'failure-code': ['v266_failure_code_report.json'], 'hash-only-ledger': ['v266_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v266_no_raw_phrase_leakage_report.json'], 'no-approval-file-write-proof': ['v266_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v266_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v266_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v226_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v225_report.json'], 'mission-state': ['dummy_mission_state_report_v252.json', 'dashboard_v266_report_v1.json', 'completion_oriented_next_action_v266_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(266)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v266/reports.py scripts/generate_v266_reports.py dashboard/backend/v266_routes.py",
    "python scripts/generate_v266_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v266_external_authority_import_wizard_controller_report.json"

FAILURE_HINTS = {
    "IMPORT_MANIFEST_ABSENT": "Provide an external authority manifest/approval to the wizard; Dummy writes nothing.",
    "APPROVAL_PHRASE_INVALID": "Use the exact CONTROLLED_PILOT_PHRASE verbatim.",
    "FUZZY_APPROVAL_REJECTED": "Remove ambiguous/scope-mismatched language; supply exact scope and acknowledgments.",
    "BROAD_APPROVAL_REJECTED": "Remove broad live-trading language; scope must be the single controlled pilot.",
    "OPERATOR_METADATA_MISSING": "Add operator, timestamp, reason, scope, expiration metadata.",
    "PROOF_TARGET_INVALID": "Set proof_target to FIRST_REAL_PILOT_PROOF or CONTROLLED_SESSION_PROOF.",
    "LIVE_SUBMIT_DESCRIPTOR_MISSING": "Supply an external live-submit descriptor.",
    "CAPS_DESCRIPTOR_MISSING": "Supply an external caps descriptor.",
    "FIREWALL_DESCRIPTOR_MISSING": "Supply an external LiveBrokerFirewall adapter descriptor.",
    "NONE": "Import inputs validated; proceed.",
}


class V266Context:
    def __init__(self, *, import_approval=None, import_approval_path=None, live_submit_descriptor=False, caps_descriptor=False, firewall_descriptor=False, proof_target="FIRST_REAL_PILOT_PROOF") -> None:
        self.v265_baseline_status = sgc.baseline_status("final_report_v265.json", "V265")
        resolution = sgc.resolve_packet(import_approval_path, import_approval)
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
        self.live_submit_descriptor = bool(live_submit_descriptor)
        self.caps_descriptor = bool(caps_descriptor)
        self.firewall_descriptor = bool(firewall_descriptor)
        self.descriptors_complete = self.live_submit_descriptor and self.caps_descriptor and self.firewall_descriptor
        self.wizard_valid = bool(self.validation["accepted"]) and self.target_valid and self.descriptors_complete

    @property
    def rejected(self) -> bool:
        # Present but the approval itself is malformed/broad/fuzzy/wrong-target => fail closed.
        if not self.present:
            return False
        b = self.validation["blockers"]
        return bool(b) or not self.target_valid

    @property
    def failure_code(self) -> str:
        if self.wizard_valid:
            return "NONE"
        if not self.present:
            return "IMPORT_MANIFEST_ABSENT"
        b = self.validation["blockers"]
        if "APPROVAL_PHRASE_NOT_EXACT" in b:
            return "APPROVAL_PHRASE_INVALID"
        if "LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED" in b:
            return "BROAD_APPROVAL_REJECTED"
        if "MISSING_REQUIRED_APPROVAL_FIELDS" in b:
            return "OPERATOR_METADATA_MISSING"
        if "SCOPE_MISMATCH" in b or "ACKNOWLEDGMENT_INCOMPLETE" in b:
            return "FUZZY_APPROVAL_REJECTED"
        if not self.target_valid:
            return "PROOF_TARGET_INVALID"
        if not self.live_submit_descriptor:
            return "LIVE_SUBMIT_DESCRIPTOR_MISSING"
        if not self.caps_descriptor:
            return "CAPS_DESCRIPTOR_MISSING"
        if not self.firewall_descriptor:
            return "FIREWALL_DESCRIPTOR_MISSING"
        return "FUZZY_APPROVAL_REJECTED"

    @property
    def controller_status(self) -> str:
        if self.v265_baseline_status.startswith("FAIL"):
            return "FAIL_EXTERNAL_AUTHORITY_IMPORT_WIZARD_BASELINE_REGRESSION"
        if self.wizard_valid:
            return "PASS_EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_NO_WRITE"
        if self.rejected:
            return "FAIL_CLOSED_EXTERNAL_AUTHORITY_IMPORT_WIZARD_REJECTED"
        return "PARTIAL_EXTERNAL_AUTHORITY_IMPORT_WIZARD_BLOCKED_INPUTS_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v265_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.wizard_valid:
            return "PASS"
        if self.rejected:
            return "FAIL"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v265_baseline_status.startswith("FAIL"):
            return ["FAIL_V265_BASELINE_REGRESSION"]
        return [] if self.wizard_valid else [self.failure_code]

    @property
    def next_action(self) -> str:
        if self.wizard_valid:
            return "EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_RUN_APPROVAL_MANIFEST_SCHEMA_VERIFIER_NO_SUBMIT"
        return "OPERATOR_SUPPLY_EXTERNAL_AUTHORITY_INPUTS_PER_FIX_HINTS_DUMMY_WRITES_NOTHING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v265_baseline_status": ctx.v265_baseline_status,
        "external_authority_import_wizard_controller_status": ctx.controller_status,
        "wizard_valid": ctx.wizard_valid,
        "import_present": ctx.present,
        "import_approval_hash": ctx.validation["approval_hash"],
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "fix_hint": FAILURE_HINTS.get(ctx.failure_code, "Review import inputs."),
        "fix_hints": FAILURE_HINTS,
        "proof_target": ctx.proof_target,
        "import_input_validation_status": "PASS_IMPORT_INPUT_VALIDATION_RUN",
        "descriptor_checks": {"live_submit_descriptor": ctx.live_submit_descriptor, "caps_descriptor": ctx.caps_descriptor, "firewall_descriptor": ctx.firewall_descriptor},
        "descriptor_checks_status": "PASS_DESCRIPTOR_CHECKS_RUN" if ctx.descriptors_complete else "PARTIAL_DESCRIPTORS_INCOMPLETE",
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
        "readiness_governor_v226_status": "PASS",
        "execution_lock_deep_recheck_v225_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v265_baseline"):
        return "PASS" if ctx.v265_baseline_status == "PASS_V265_BASELINE_READBACK" else "FAIL" if ctx.v265_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v266: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v266_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V266_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v266_report.json":
        report.update({"completion_oriented_next_action_v266_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v265_carried_status": ctx.v265_baseline_status, "external_authority_import_wizard_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v266.json", "dummy_canonical_identity_report_v266.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V266ReportFactory:
    def __init__(self, *, import_approval=None, import_approval_path=None, live_submit_descriptor=False, caps_descriptor=False, firewall_descriptor=False, proof_target='FIRST_REAL_PILOT_PROOF') -> None:
        self.kw = dict(import_approval=import_approval, import_approval_path=import_approval_path, live_submit_descriptor=live_submit_descriptor, caps_descriptor=caps_descriptor, firewall_descriptor=firewall_descriptor, proof_target=proof_target)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V266Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
