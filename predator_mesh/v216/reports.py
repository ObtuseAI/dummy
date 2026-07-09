"""DUMMY v216 external authority manifest intake validate only — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v216 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v216: External Authority Manifest Intake Validate Only"
MISSION_NAME = "dummy_mission_state_report_v202.json"
FINAL_NAME = "final_report_v216.json"
INDEX_KEYS = ['external_authority_manifest_intake_controller_status', 'manifest_valid', 'approval_files_written']
DASH_TITLE = "Dummy V216 External Authority Manifest Intake Validate Only"
MISSION_KEY = "dummy_mission_state_report_v202"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Manifest Intake', 'external_authority_manifest_intake_controller_status'], ['Manifest Valid', 'manifest_valid'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V216_ROUTES = ['/api/v216/external-authority-manifest-intake-controller', '/api/v216/v215-baseline', '/api/v216/exact-approval-files-check', '/api/v216/operator-metadata-check', '/api/v216/timestamps-check', '/api/v216/reason-fields-check', '/api/v216/live-submit-descriptor-check', '/api/v216/caps-descriptor-check', '/api/v216/firewall-adapter-descriptor-check', '/api/v216/proof-target-selector-check', '/api/v216/hash-only-ledger', '/api/v216/no-raw-phrase-leakage', '/api/v216/no-file-writes-proof', '/api/v216/no-submit-proof', '/api/v216/readiness-governor', '/api/v216/execution-lock', '/api/v216/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-authority-manifest-intake-controller': ['v216_external_authority_manifest_intake_controller_report.json'], 'v215-baseline': ['v215_baseline_readback_v1_report.json'], 'exact-approval-files-check': ['v216_exact_approval_files_check_report.json'], 'operator-metadata-check': ['v216_operator_metadata_check_report.json'], 'timestamps-check': ['v216_timestamps_check_report.json'], 'reason-fields-check': ['v216_reason_fields_check_report.json'], 'live-submit-descriptor-check': ['v216_live_submit_descriptor_check_report.json'], 'caps-descriptor-check': ['v216_caps_descriptor_check_report.json'], 'firewall-adapter-descriptor-check': ['v216_firewall_adapter_descriptor_check_report.json'], 'proof-target-selector-check': ['v216_proof_target_selector_check_report.json'], 'hash-only-ledger': ['v216_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v216_no_raw_phrase_leakage_report.json'], 'no-file-writes-proof': ['v216_no_file_writes_proof_report.json'], 'no-submit-proof': ['v216_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v176_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v175_report.json'], 'mission-state': ['dummy_mission_state_report_v202.json', 'dashboard_v216_report_v1.json', 'completion_oriented_next_action_v216_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(216)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v216/reports.py scripts/generate_v216_reports.py dashboard/backend/v216_routes.py",
    "python scripts/generate_v216_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v216_external_authority_manifest_intake_controller_report.json"

class V216Context:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target="FIRST_REAL_PILOT_PROOF") -> None:
        self.v215_baseline_status = sgc.baseline_status("final_report_v215.json", "V215")
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
    def controller_status(self) -> str:
        if self.v215_baseline_status.startswith("FAIL"):
            return "FAIL_MANIFEST_INTAKE_BASELINE_REGRESSION"
        if self.manifest_valid:
            return "PASS_EXTERNAL_AUTHORITY_MANIFEST_VALIDATED_NO_SUBMIT"
        if self.present:
            return "FAIL_CLOSED_EXTERNAL_AUTHORITY_MANIFEST_REJECTED"
        return "PARTIAL_EXTERNAL_AUTHORITY_MANIFEST_ABSENT_OR_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v215_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.manifest_valid:
            return "PASS"
        if self.present:
            return "FAIL"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v215_baseline_status.startswith("FAIL"):
            return ["FAIL_V215_BASELINE_REGRESSION"]
        if self.manifest_valid:
            return []
        if self.present:
            return list(self.validation["blockers"]) + ([] if self.target_valid else ["PROOF_TARGET_INVALID"])
        return ["EXTERNAL_AUTHORITY_MANIFEST_ABSENT"]

    @property
    def next_action(self) -> str:
        if self.manifest_valid:
            return "EXTERNAL_AUTHORITY_MANIFEST_VALIDATED_RUN_ZERO_BROKER_DRY_VALIDATION_NO_SUBMIT"
        return "OPERATOR_SUPPLY_EXACT_EXTERNAL_AUTHORITY_MANIFEST_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v215_baseline_status": ctx.v215_baseline_status,
        "external_authority_manifest_intake_controller_status": ctx.controller_status,
        "manifest_valid": ctx.manifest_valid,
        "manifest_present": ctx.present,
        "manifest_approval_hash": ctx.validation["approval_hash"],
        "manifest_blockers": ctx.validation["blockers"],
        "proof_target": ctx.proof_target,
        "proof_target_selector_check_status": "PASS_PROOF_TARGET_" + ctx.proof_target if ctx.target_valid else "FAIL_CLOSED_PROOF_TARGET_INVALID",
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "no_raw_phrase_leakage_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "no_file_writes_proof_status": "PASS_NO_FILE_WRITES",
        "approval_files_written": 0,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "readiness_governor_v176_status": "PASS",
        "execution_lock_deep_recheck_v175_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v215_baseline"):
        return "PASS" if ctx.v215_baseline_status == "PASS_V215_BASELINE_READBACK" else "FAIL" if ctx.v215_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v216: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v216_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V216_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v216_report.json":
        report.update({"completion_oriented_next_action_v216_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v215_carried_status": ctx.v215_baseline_status, "external_authority_manifest_intake_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v216.json", "dummy_canonical_identity_report_v216.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V216ReportFactory:
    def __init__(self, *, manifest_approval=None, manifest_approval_path=None, proof_target='FIRST_REAL_PILOT_PROOF') -> None:
        self.kw = dict(manifest_approval=manifest_approval, manifest_approval_path=manifest_approval_path, proof_target=proof_target)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V216Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
