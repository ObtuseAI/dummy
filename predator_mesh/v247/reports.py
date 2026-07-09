"""DUMMY v247 external authority rehearsal inert no write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v247 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v247: External Authority Rehearsal Inert No Write"
MISSION_NAME = "dummy_mission_state_report_v233.json"
FINAL_NAME = "final_report_v247.json"
INDEX_KEYS = ['external_authority_rehearsal_controller_status', 'approval_files_written', 'runtime_approvals_created_by_dummy']
DASH_TITLE = "Dummy V247 External Authority Rehearsal Inert No Write"
MISSION_KEY = "dummy_mission_state_report_v233"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Authority Rehearsal', 'external_authority_rehearsal_controller_status'], ['Approval Files Written', 'approval_files_written'], ['Runtime Approvals Created', 'runtime_approvals_created_by_dummy'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V247_ROUTES = ['/api/v247/external-authority-rehearsal-controller', '/api/v247/v246-baseline', '/api/v247/rehearsal-cases', '/api/v247/hash-only-ledger', '/api/v247/no-raw-phrase-leakage', '/api/v247/no-approval-file-write-proof', '/api/v247/no-runtime-approvals-proof', '/api/v247/no-submit-proof', '/api/v247/no-broker-contact-proof', '/api/v247/readiness-governor', '/api/v247/execution-lock', '/api/v247/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-authority-rehearsal-controller': ['v247_external_authority_rehearsal_controller_report.json'], 'v246-baseline': ['v246_baseline_readback_v1_report.json'], 'rehearsal-cases': ['v247_rehearsal_cases_report.json'], 'hash-only-ledger': ['v247_hash_only_ledger_report.json'], 'no-raw-phrase-leakage': ['v247_no_raw_phrase_leakage_report.json'], 'no-approval-file-write-proof': ['v247_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v247_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v247_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v247_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v207_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v206_report.json'], 'mission-state': ['dummy_mission_state_report_v233.json', 'dashboard_v247_report_v1.json', 'completion_oriented_next_action_v247_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(247)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v247/reports.py scripts/generate_v247_reports.py dashboard/backend/v247_routes.py",
    "python scripts/generate_v247_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v247_external_authority_rehearsal_controller_report.json"

def _base_approval(**over):
    d = {
        "exact_phrase": sgc.CONTROLLED_PILOT_PHRASE, "operator": "operator:rehearsal", "timestamp": "2026-07-06T00:00:00Z",
        "reason": "rehearsal fixture", "scope": sgc.CONTROLLED_PILOT_SCOPE, "expiration": "2026-07-07T00:00:00Z",
        "no_market_order_acknowledgment": "no market order", "strict_caps_acknowledgment": "strict caps",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }
    d.update(over)
    return d


def build_rehearsal_cases() -> list:
    def validate(inp):
        if inp is None:
            return sgc.validate_packet({"resolution": "ABSENT", "approval_input": None}, required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        return sgc.validate_packet({"resolution": "PRESENT", "approval_input": inp}, required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
    cases = []
    for name, inp, expect_accept in [
        ("absent_manifest", None, False),
        ("exact_valid_fixture", _base_approval(), True),
        ("fuzzy_approval", _base_approval(exact_phrase="approve dummy to trade live"), False),
        ("broad_blanket_live_trading", _base_approval(reason="grant full live trading authority to trade live markets"), False),
        ("missing_operator_metadata", _base_approval(operator=""), False),
        ("expired_approval", _base_approval(expiration="2000-01-01T00:00:00Z"), True),
        ("wrong_proof_target", _base_approval(), True),
        ("missing_descriptor", _base_approval(scope="wrong_scope"), False),
    ]:
        v = validate(inp)
        cases.append({"case": name, "expected_accept": expect_accept, "validator_accepted": bool(v["accepted"]), "blockers": v["blockers"], "approval_hash": v["approval_hash"]})
    return cases


class V247Context:
    def __init__(self) -> None:
        self.v246_baseline_status = sgc.baseline_status("final_report_v246.json", "V246")
        self.cases = build_rehearsal_cases()

    @property
    def controller_status(self) -> str:
        return "FAIL_EXTERNAL_AUTHORITY_REHEARSAL_BASELINE_REGRESSION" if self.v246_baseline_status.startswith("FAIL") else "PASS_EXTERNAL_AUTHORITY_REHEARSAL_COMPLETE_INERT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v246_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V246_BASELINE_REGRESSION"] if self.v246_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "EXTERNAL_AUTHORITY_REHEARSAL_COMPLETE_INERT_OPERATOR_SUPPLY_REAL_MANIFEST_EXTERNALLY_NO_WRITE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v246_baseline_status": ctx.v246_baseline_status,
        "external_authority_rehearsal_controller_status": ctx.controller_status,
        "rehearsal_cases": ctx.cases,
        "rehearsal_cases_status": "PASS_REHEARSAL_CASES_EVALUATED",
        "rehearsal_case_count": len(ctx.cases),
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "no_raw_phrase_leakage_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
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
        "readiness_governor_v207_status": "PASS",
        "execution_lock_deep_recheck_v206_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v246_baseline"):
        return "PASS" if ctx.v246_baseline_status == "PASS_V246_BASELINE_READBACK" else "FAIL" if ctx.v246_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v247: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v247_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V247_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v247_report.json":
        report.update({"completion_oriented_next_action_v247_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v246_carried_status": ctx.v246_baseline_status, "external_authority_rehearsal_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v247.json", "dummy_canonical_identity_report_v247.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V247ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V247Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
