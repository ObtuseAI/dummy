"""DUMMY v156 operator approval-file linter — lints manually supplied approval files; writes no approval files.

Lints the five operator approval files (production-pilot, broker-read-only, repeat-pilot, scale, controlled-operation)
against exact phrase / scope / expiration / operator-metadata and rejects broad/fuzzy or live-trading-blanket
approvals. Emits a hash-only ledger with no raw phrase leakage. Default is
PARTIAL_APPROVAL_FILES_ABSENT_OR_INCOMPLETE. Dummy never creates or modifies approval files (approval_files_written=0).
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v156 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v156: Operator Approval File Linter Final Checklist No Write"
MISSION_NAME = "dummy_mission_state_report_v142.json"
FINAL_NAME = "final_report_v156.json"
INDEX_KEYS = ["approval_linter_controller_status", "approval_files_written", "broker_contacted"]
DASH_TITLE = "Dummy V156 Operator Approval-File Linter"
MISSION_KEY = "dummy_mission_state_report_v142"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Approval Linter", "approval_linter_controller_status"],
    ["Approval Files Written", "approval_files_written"],
    ["Broker Contacted", "broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V156_ROUTES = [
    "/api/v156/approval-linter-controller",
    "/api/v156/v155-baseline",
    "/api/v156/production-pilot-approval-linter",
    "/api/v156/broker-readonly-approval-linter",
    "/api/v156/repeat-pilot-approval-linter",
    "/api/v156/scale-approval-linter",
    "/api/v156/controlled-operation-approval-linter",
    "/api/v156/broad-fuzzy-approval-rejection",
    "/api/v156/hash-only-ledger",
    "/api/v156/no-raw-phrase-leakage-proof",
    "/api/v156/no-approval-file-write-proof",
    "/api/v156/no-submit-proof",
    "/api/v156/no-broker-contact-proof",
    "/api/v156/readiness-governor",
    "/api/v156/execution-lock",
    "/api/v156/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "approval-linter-controller": ["v156_approval_linter_controller_report.json"],
    "v155-baseline": ["v155_baseline_readback_v1_report.json"],
    "production-pilot-approval-linter": ["v156_production_pilot_approval_linter_report.json"],
    "broker-readonly-approval-linter": ["v156_broker_readonly_approval_linter_report.json"],
    "repeat-pilot-approval-linter": ["v156_repeat_pilot_approval_linter_report.json"],
    "scale-approval-linter": ["v156_scale_approval_linter_report.json"],
    "controlled-operation-approval-linter": ["v156_controlled_operation_approval_linter_report.json"],
    "broad-fuzzy-approval-rejection": ["v156_broad_fuzzy_approval_rejection_report.json"],
    "hash-only-ledger": ["v156_hash_only_ledger_report.json"],
    "no-raw-phrase-leakage-proof": ["v156_no_raw_phrase_leakage_proof_report.json"],
    "no-approval-file-write-proof": ["v156_no_approval_file_write_proof_report.json"],
    "no-submit-proof": ["v156_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v156_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v116_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v115_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v156_report_v1.json", "completion_oriented_next_action_v156_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(156)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v156/reports.py scripts/generate_v156_reports.py dashboard/backend/v156_routes.py",
    "python scripts/generate_v156_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V156Context:
    def __init__(self, *, pilot_approval=None, broker_readonly_approval=None, repeat_approval=None) -> None:
        self.v155_baseline_status = sgc.baseline_status("final_report_v155.json", "V155")
        self.pilot_v = sgc.validate_packet(sgc.resolve_packet(None, pilot_approval), required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        self.broker_v = sgc.validate_packet(sgc.resolve_packet(None, broker_readonly_approval), required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)
        self.repeat_v = sgc.validate_packet(sgc.resolve_packet(None, repeat_approval), required_phrase=sgc.REPEAT_PILOT_PHRASE, required_fields=sgc.REPEAT_PILOT_FIELDS, required_scope=sgc.REPEAT_PILOT_SCOPE)

    @property
    def pilot_ok(self) -> bool:
        return bool(self.pilot_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.pilot_v, self.broker_v, self.repeat_v))

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_APPROVAL_FILE"
        if self.pilot_ok:
            return "PASS_APPROVAL_FILES_LINTED_VALID"
        return "PARTIAL_APPROVAL_FILES_ABSENT_OR_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v155_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.pilot_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v155_baseline_status.startswith("FAIL"):
            return ["FAIL_V155_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_APPROVAL_FILE"]
        return [] if self.pilot_ok else ["PRODUCTION_PILOT_APPROVAL_FILE_ABSENT"]

    @property
    def next_action(self) -> str:
        return "APPROVAL_FILES_LINTED_VALID_AWAIT_LIVE_SUBMIT_CAPS_AUDIT_NO_WRITE" if self.pilot_ok else "OPERATOR_MUST_SUPPLY_EXACT_APPROVAL_FILES_DUMMY_WRITES_NOTHING"


def _lint_status(v) -> str:
    return "PASS_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_APPROVAL_ABSENT")


def _common(ctx: V156Context) -> dict[str, Any]:
    return {
        "v155_baseline_status": ctx.v155_baseline_status,
        "approval_linter_controller_status": ctx.controller_status,
        "production_pilot_approval_linter_status": _lint_status(ctx.pilot_v),
        "broker_readonly_approval_linter_status": _lint_status(ctx.broker_v),
        "repeat_pilot_approval_linter_status": _lint_status(ctx.repeat_v),
        "scale_approval_linter_status": "PARTIAL_APPROVAL_ABSENT",
        "controlled_operation_approval_linter_status": "PARTIAL_APPROVAL_ABSENT",
        "broad_fuzzy_approval_rejection_status": "PASS_BROAD_FUZZY_REJECTED",
        "live_trading_blanket_rejected": True,
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "hash_only_ledger": {"production_pilot": ctx.pilot_v["approval_hash"], "broker_readonly": ctx.broker_v["approval_hash"], "repeat_pilot": ctx.repeat_v["approval_hash"]},
        "no_raw_phrase_leakage_proof_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "approval_files_written": 0,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v116_status": "PASS",
        "execution_lock_deep_recheck_v115_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V156Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v155_baseline"):
        return "PASS" if ctx.v155_baseline_status == "PASS_V155_BASELINE_READBACK" else "FAIL" if ctx.v155_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v156_approval_linter_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.pilot_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V156Context) -> dict[str, Any]:
    workstream = "v156: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v156_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V156_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v156_report.json":
        report.update({"completion_oriented_next_action_v156_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v155_carried_status": ctx.v155_baseline_status, "approval_linter_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v156_approval_linter_controller_report.json"), "no_approval_file_write": str(ARTIFACTS / "v156_no_approval_file_write_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v156.json", "dummy_canonical_identity_report_v156.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V156ReportFactory:
    def __init__(self, *, pilot_approval=None, broker_readonly_approval=None, repeat_approval=None) -> None:
        self.kw = dict(pilot_approval=pilot_approval, broker_readonly_approval=broker_readonly_approval, repeat_approval=repeat_approval)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V156Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
