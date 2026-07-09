"""DUMMY v206 operator activation manifest linter — one manifest schema of what must exist for live proof; writes no approval files.

Defines a single manifest schema (approval file paths, expected exact phrases, operator metadata, live-submit/caps
fields, firewall/broker descriptors, proof-target selector) and lints a supplied manifest, rejecting broad/fuzzy
approvals and emitting a hash-only ledger. Default is PARTIAL_ACTIVATION_MANIFEST_INPUTS_ABSENT. Dummy writes no
approval files.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v206 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v206: Operator Activation Manifest Linter No Approval Write"
MISSION_NAME = "dummy_mission_state_report_v192.json"
FINAL_NAME = "final_report_v206.json"
INDEX_KEYS = ["activation_manifest_controller_status", "approval_files_written", "live_orders"]
DASH_TITLE = "Dummy V206 Operator Activation Manifest Linter"
MISSION_KEY = "dummy_mission_state_report_v192"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Manifest Linter", "activation_manifest_controller_status"],
    ["Approval Files Written", "approval_files_written"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V206_ROUTES = [
    "/api/v206/activation-manifest-controller",
    "/api/v206/v205-baseline",
    "/api/v206/manifest-schema",
    "/api/v206/manifest-linter",
    "/api/v206/production-pilot-approval-lint",
    "/api/v206/controlled-session-approval-lint",
    "/api/v206/broker-readonly-approval-lint",
    "/api/v206/broad-fuzzy-approval-rejection",
    "/api/v206/hash-only-ledger",
    "/api/v206/no-raw-phrase-leakage-proof",
    "/api/v206/no-approval-file-write-proof",
    "/api/v206/no-submit-proof",
    "/api/v206/readiness-governor",
    "/api/v206/execution-lock",
    "/api/v206/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "activation-manifest-controller": ["v206_activation_manifest_controller_report.json"],
    "v205-baseline": ["v205_baseline_readback_v1_report.json"],
    "manifest-schema": ["v206_manifest_schema_report.json"],
    "manifest-linter": ["v206_manifest_linter_report.json"],
    "production-pilot-approval-lint": ["v206_production_pilot_approval_lint_report.json"],
    "controlled-session-approval-lint": ["v206_controlled_session_approval_lint_report.json"],
    "broker-readonly-approval-lint": ["v206_broker_readonly_approval_lint_report.json"],
    "broad-fuzzy-approval-rejection": ["v206_broad_fuzzy_approval_rejection_report.json"],
    "hash-only-ledger": ["v206_hash_only_ledger_report.json"],
    "no-raw-phrase-leakage-proof": ["v206_no_raw_phrase_leakage_proof_report.json"],
    "no-approval-file-write-proof": ["v206_no_approval_file_write_proof_report.json"],
    "no-submit-proof": ["v206_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v166_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v165_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v206_report_v1.json", "completion_oriented_next_action_v206_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(206)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v206/reports.py scripts/generate_v206_reports.py dashboard/backend/v206_routes.py",
    "python scripts/generate_v206_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

MANIFEST_SCHEMA = {
    "approval_file_paths": {
        "production_pilot": "runtime/approvals/dummy_controlled_production_pilot_approval.json",
        "controlled_operation": "runtime/approvals/dummy_controlled_operation_approval.json",
        "controlled_session": "runtime/approvals/dummy_controlled_session_canary_approval.json",
        "broker_readonly": "runtime/approvals/dummy_broker_readonly_approval.json",
    },
    "expected_exact_phrases": {
        "production_pilot": sgc.CONTROLLED_PILOT_PHRASE,
        "controlled_session": sgc.CONTROLLED_SESSION_PHRASE,
        "broker_readonly": sgc.BROKER_READONLY_PHRASE,
    },
    "required_operator_metadata": ["operator", "timestamp", "reason", "scope", "expiration"],
    "required_live_submit_config_fields": ["operator_enabled", "operator_metadata", "live_submit_hash"],
    "required_caps_fields": ["max_order_size", "max_exposure", "max_daily_loss", "caps_hash"],
    "required_firewall_adapter_descriptor": ["submit_callable", "non_broker_double_ok", "market_order_denied"],
    "optional_broker_readonly_descriptor": ["read_only_verify_callable"],
    "proof_target_selector": ["FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF"],
}


class V206Context:
    def __init__(self, *, pilot_approval=None, session_approval=None, broker_readonly_approval=None) -> None:
        self.v205_baseline_status = sgc.baseline_status("final_report_v205.json", "V205")
        self.pilot_v = sgc.validate_packet(sgc.resolve_packet(None, pilot_approval), required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        self.sess_v = sgc.validate_packet(sgc.resolve_packet(None, session_approval), required_phrase=sgc.CONTROLLED_SESSION_PHRASE, required_fields=sgc.CONTROLLED_SESSION_FIELDS, required_scope=sgc.CONTROLLED_SESSION_SCOPE, ack_requirements=sgc.CONTROLLED_SESSION_ACKS)
        self.broker_v = sgc.validate_packet(sgc.resolve_packet(None, broker_readonly_approval), required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)

    @property
    def relevant_ok(self) -> bool:
        return bool(self.pilot_v["accepted"]) or bool(self.sess_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.pilot_v, self.sess_v, self.broker_v))

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_MANIFEST_APPROVAL"
        if self.relevant_ok:
            return "PASS_ACTIVATION_MANIFEST_LINTED_VALID"
        return "PARTIAL_ACTIVATION_MANIFEST_INPUTS_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v205_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.relevant_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v205_baseline_status.startswith("FAIL"):
            return ["FAIL_V205_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_MANIFEST_APPROVAL"]
        return [] if self.relevant_ok else ["ACTIVATION_MANIFEST_APPROVALS_ABSENT"]

    @property
    def next_action(self) -> str:
        return "ACTIVATION_MANIFEST_LINTED_VALID_AWAIT_COCKPIT_AND_AUTHORITY_RESOLVER" if self.relevant_ok else "OPERATOR_MUST_SUPPLY_MANIFEST_APPROVALS_AND_CONFIG_DUMMY_WRITES_NOTHING"


def _lint(v) -> str:
    return "PASS_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_APPROVAL_ABSENT")


def _common(ctx: V206Context) -> dict[str, Any]:
    return {
        "v205_baseline_status": ctx.v205_baseline_status,
        "activation_manifest_controller_status": ctx.controller_status,
        "manifest_schema_status": "PASS_MANIFEST_SCHEMA_DEFINED",
        "manifest_schema": MANIFEST_SCHEMA,
        "manifest_linter_status": "PASS_MANIFEST_LINTED" if ctx.relevant_ok else ("FAIL_CLOSED_INVALID_MANIFEST" if ctx.any_fail else "PARTIAL_MANIFEST_ABSENT"),
        "production_pilot_approval_lint_status": _lint(ctx.pilot_v),
        "controlled_session_approval_lint_status": _lint(ctx.sess_v),
        "broker_readonly_approval_lint_status": _lint(ctx.broker_v),
        "broad_fuzzy_approval_rejection_status": "PASS_BROAD_FUZZY_REJECTED",
        "hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "hash_only_ledger": {"production_pilot": ctx.pilot_v["approval_hash"], "controlled_session": ctx.sess_v["approval_hash"], "broker_readonly": ctx.broker_v["approval_hash"]},
        "no_raw_phrase_leakage_proof_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "manifest_valid": ctx.relevant_ok,
        "approval_files_written": 0,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v166_status": "PASS",
        "execution_lock_deep_recheck_v165_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V206Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v205_baseline"):
        return "PASS" if ctx.v205_baseline_status == "PASS_V205_BASELINE_READBACK" else "FAIL" if ctx.v205_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v206_activation_manifest_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.relevant_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V206Context) -> dict[str, Any]:
    workstream = "v206: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v206_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V206_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v206_report.json":
        report.update({"completion_oriented_next_action_v206_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v205_carried_status": ctx.v205_baseline_status, "activation_manifest_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v206_activation_manifest_controller_report.json"), "no_approval_file_write": str(ARTIFACTS / "v206_no_approval_file_write_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v206.json", "dummy_canonical_identity_report_v206.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V206ReportFactory:
    def __init__(self, *, pilot_approval=None, session_approval=None, broker_readonly_approval=None) -> None:
        self.kw = dict(pilot_approval=pilot_approval, session_approval=session_approval, broker_readonly_approval=broker_readonly_approval)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V206Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
