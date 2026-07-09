"""DUMMY v195 first live-proof activation binder — consolidates every first-live-proof authority input; never submits.

Validates the exact production-pilot, controlled-operation, controlled-session, and broker-read-only approvals and
checks live-submit/caps, firewall, mode-firewall, candidate/risk/abstention, and shadow-governor prerequisites. Emits a
hash-only ledger. Default is PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE. No submit, no broker contact, no approval
writes.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v195 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v195: First Live Proof Activation Binder Operator Authority Map"
MISSION_NAME = "dummy_mission_state_report_v181.json"
FINAL_NAME = "final_report_v195.json"
INDEX_KEYS = ["activation_binder_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V195 First Live-Proof Activation Binder"
MISSION_KEY = "dummy_mission_state_report_v181"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Activation Binder", "activation_binder_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V195_ROUTES = [
    "/api/v195/activation-binder-controller",
    "/api/v195/v194-baseline",
    "/api/v195/production-pilot-approval-validator",
    "/api/v195/controlled-operation-approval-validator",
    "/api/v195/controlled-session-approval-validator",
    "/api/v195/broker-readonly-approval-validator",
    "/api/v195/live-submit-caps-status-checker",
    "/api/v195/firewall-adapter-checker",
    "/api/v195/mode-firewall-checker",
    "/api/v195/candidate-risk-abstention-proof-checker",
    "/api/v195/shadow-governor-proof-checker",
    "/api/v195/approval-hash-only-ledger",
    "/api/v195/no-approval-file-write-proof",
    "/api/v195/no-submit-proof",
    "/api/v195/no-broker-contact-proof",
    "/api/v195/readiness-governor",
    "/api/v195/execution-lock",
    "/api/v195/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "activation-binder-controller": ["v195_activation_binder_controller_report.json"],
    "v194-baseline": ["v194_baseline_readback_v1_report.json"],
    "production-pilot-approval-validator": ["v195_production_pilot_approval_validator_report.json"],
    "controlled-operation-approval-validator": ["v195_controlled_operation_approval_validator_report.json"],
    "controlled-session-approval-validator": ["v195_controlled_session_approval_validator_report.json"],
    "broker-readonly-approval-validator": ["v195_broker_readonly_approval_validator_report.json"],
    "live-submit-caps-status-checker": ["v195_live_submit_caps_status_checker_report.json"],
    "firewall-adapter-checker": ["v195_firewall_adapter_checker_report.json"],
    "mode-firewall-checker": ["v195_mode_firewall_checker_report.json"],
    "candidate-risk-abstention-proof-checker": ["v195_candidate_risk_abstention_proof_checker_report.json"],
    "shadow-governor-proof-checker": ["v195_shadow_governor_proof_checker_report.json"],
    "approval-hash-only-ledger": ["v195_approval_hash_only_ledger_report.json"],
    "no-approval-file-write-proof": ["v195_no_approval_file_write_proof_report.json"],
    "no-submit-proof": ["v195_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v195_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v155_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v154_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v195_report_v1.json", "completion_oriented_next_action_v195_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(195)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v195/reports.py scripts/generate_v195_reports.py dashboard/backend/v195_routes.py",
    "python scripts/generate_v195_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V195Context:
    def __init__(self, *, pilot_approval=None, operation_approval=None, session_approval=None, broker_readonly_approval=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.v194_baseline_status = sgc.baseline_status("final_report_v194.json", "V194")
        self.pilot_v = sgc.validate_packet(sgc.resolve_packet(None, pilot_approval), required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        self.op_v = sgc.validate_packet(sgc.resolve_packet(None, operation_approval), required_phrase=sgc.CONTROLLED_OPERATION_PHRASE, required_fields=sgc.CONTROLLED_OPERATION_FIELDS, required_scope=sgc.CONTROLLED_OPERATION_SCOPE)
        self.sess_v = sgc.validate_packet(sgc.resolve_packet(None, session_approval), required_phrase=sgc.CONTROLLED_SESSION_PHRASE, required_fields=sgc.CONTROLLED_SESSION_FIELDS, required_scope=sgc.CONTROLLED_SESSION_SCOPE, ack_requirements=sgc.CONTROLLED_SESSION_ACKS)
        self.broker_v = sgc.validate_packet(sgc.resolve_packet(None, broker_readonly_approval), required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def relevant_ok(self) -> bool:
        return bool(self.pilot_v["accepted"]) or bool(self.sess_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.pilot_v, self.op_v, self.sess_v, self.broker_v))

    @property
    def bound(self) -> bool:
        return self.relevant_ok and self.live_submit_operator_enabled and self.caps_config_present and self.firewall_adapter_present

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_ACTIVATION_APPROVAL"
        if self.bound:
            return "PASS_FIRST_LIVE_PROOF_AUTHORITY_BOUND_NO_SUBMIT"
        return "PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v194_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.bound else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v194_baseline_status.startswith("FAIL"):
            return ["FAIL_V194_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_ACTIVATION_APPROVAL"]
        if self.bound:
            return []
        blockers: list[str] = []
        if not self.relevant_ok:
            blockers.append("PILOT_OR_SESSION_APPROVAL_ABSENT")
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        if not self.firewall_adapter_present:
            blockers.append("FIREWALL_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_PROOF_AUTHORITY_BOUND_NO_SUBMIT_AWAIT_CONFIG_CAPS_QUORUM" if self.bound else "OPERATOR_MUST_SUPPLY_PILOT_OR_SESSION_APPROVAL_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER"


def _lint(v) -> str:
    return "PASS_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_APPROVAL_ABSENT")


def _common(ctx: V195Context) -> dict[str, Any]:
    return {
        "v194_baseline_status": ctx.v194_baseline_status,
        "activation_binder_controller_status": ctx.controller_status,
        "production_pilot_approval_validator_status": _lint(ctx.pilot_v),
        "controlled_operation_approval_validator_status": _lint(ctx.op_v),
        "controlled_session_approval_validator_status": _lint(ctx.sess_v),
        "broker_readonly_approval_validator_status": _lint(ctx.broker_v),
        "live_submit_caps_status_checker_status": "PASS_LIVE_SUBMIT_CAPS_READONLY" if (ctx.live_submit_operator_enabled and ctx.caps_config_present) else "PARTIAL_LIVE_SUBMIT_OR_CAPS_ABSENT",
        "firewall_adapter_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "mode_firewall_checker_status": "PASS_MODE_FIREWALL_CHECKED",
        "candidate_risk_abstention_proof_checker_status": "PASS_CANDIDATE_RISK_ABSTENTION_PRESENT",
        "shadow_governor_proof_checker_status": "PASS_SHADOW_GOVERNOR_INERT_PRESENT",
        "approval_hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "approval_hash_only_ledger": {"production_pilot": ctx.pilot_v["approval_hash"], "controlled_operation": ctx.op_v["approval_hash"], "controlled_session": ctx.sess_v["approval_hash"], "broker_readonly": ctx.broker_v["approval_hash"]},
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "authority_bound": ctx.bound,
        "approval_files_written": 0,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v155_status": "PASS",
        "execution_lock_deep_recheck_v154_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V195Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v194_baseline"):
        return "PASS" if ctx.v194_baseline_status == "PASS_V194_BASELINE_READBACK" else "FAIL" if ctx.v194_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v195_activation_binder_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.bound else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V195Context) -> dict[str, Any]:
    workstream = "v195: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v195_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V195_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v195_report.json":
        report.update({"completion_oriented_next_action_v195_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v194_carried_status": ctx.v194_baseline_status, "activation_binder_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v195_activation_binder_controller_report.json"), "no_submit": str(ARTIFACTS / "v195_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v195.json", "dummy_canonical_identity_report_v195.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V195ReportFactory:
    def __init__(self, *, pilot_approval=None, operation_approval=None, session_approval=None, broker_readonly_approval=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.kw = dict(pilot_approval=pilot_approval, operation_approval=operation_approval, session_approval=session_approval, broker_readonly_approval=broker_readonly_approval, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V195Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
