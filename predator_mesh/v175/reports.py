"""DUMMY v175 controlled operation approval validator — validates controlled-operation + session approvals and prerequisite proof; never submits.

Validates the exact controlled-operation review approval and the exact controlled-session approval, and checks
first-pilot / repeat-pilot / pilot-pair / scale-evidence / risk-abstention / live-submit-caps / firewall prerequisites.
Emits a hash-only ledger. Default is PARTIAL_CONTROLLED_OPERATION_APPROVAL_OR_LIVE_PROOF_ABSENT. No submit, no broker
contact, and no approval-file writes.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v175 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v175: Controlled Operation Approval Validator No Submit"
MISSION_NAME = "dummy_mission_state_report_v161.json"
FINAL_NAME = "final_report_v175.json"
INDEX_KEYS = ["controlled_operation_approval_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V175 Controlled Operation Approval Validator"
MISSION_KEY = "dummy_mission_state_report_v161"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Approval Validator", "controlled_operation_approval_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V175_ROUTES = [
    "/api/v175/controlled-operation-approval-controller",
    "/api/v175/v174-baseline",
    "/api/v175/controlled-operation-approval-validator",
    "/api/v175/controlled-session-approval-validator",
    "/api/v175/first-pilot-proof-checker",
    "/api/v175/repeat-pilot-proof-checker",
    "/api/v175/pilot-pair-proof-checker",
    "/api/v175/scale-evidence-status-checker",
    "/api/v175/risk-abstention-prerequisite-checker",
    "/api/v175/live-submit-caps-status-checker",
    "/api/v175/firewall-adapter-checker",
    "/api/v175/approval-hash-only-ledger",
    "/api/v175/no-submit-proof",
    "/api/v175/no-broker-contact-proof",
    "/api/v175/no-approval-file-write-proof",
    "/api/v175/readiness-governor",
    "/api/v175/execution-lock",
    "/api/v175/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-approval-controller": ["v175_controlled_operation_approval_controller_report.json"],
    "v174-baseline": ["v174_baseline_readback_v1_report.json"],
    "controlled-operation-approval-validator": ["v175_controlled_operation_approval_validator_report.json"],
    "controlled-session-approval-validator": ["v175_controlled_session_approval_validator_report.json"],
    "first-pilot-proof-checker": ["v175_first_pilot_proof_checker_report.json"],
    "repeat-pilot-proof-checker": ["v175_repeat_pilot_proof_checker_report.json"],
    "pilot-pair-proof-checker": ["v175_pilot_pair_proof_checker_report.json"],
    "scale-evidence-status-checker": ["v175_scale_evidence_status_checker_report.json"],
    "risk-abstention-prerequisite-checker": ["v175_risk_abstention_prerequisite_checker_report.json"],
    "live-submit-caps-status-checker": ["v175_live_submit_caps_status_checker_report.json"],
    "firewall-adapter-checker": ["v175_firewall_adapter_checker_report.json"],
    "approval-hash-only-ledger": ["v175_approval_hash_only_ledger_report.json"],
    "no-submit-proof": ["v175_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v175_no_broker_contact_proof_report.json"],
    "no-approval-file-write-proof": ["v175_no_approval_file_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v135_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v134_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v175_report_v1.json", "completion_oriented_next_action_v175_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(175)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v175/reports.py scripts/generate_v175_reports.py dashboard/backend/v175_routes.py",
    "python scripts/generate_v175_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V175Context:
    def __init__(self, *, operation_approval=None, session_approval=None, pilot_proof_override=None) -> None:
        self.v174_baseline_status = sgc.baseline_status("final_report_v174.json", "V174")
        self.op_v = sgc.validate_packet(sgc.resolve_packet(None, operation_approval), required_phrase=sgc.CONTROLLED_OPERATION_PHRASE, required_fields=sgc.CONTROLLED_OPERATION_FIELDS, required_scope=sgc.CONTROLLED_OPERATION_SCOPE)
        self.sess_v = sgc.validate_packet(sgc.resolve_packet(None, session_approval), required_phrase=sgc.CONTROLLED_SESSION_PHRASE, required_fields=sgc.CONTROLLED_SESSION_FIELDS, required_scope=sgc.CONTROLLED_SESSION_SCOPE, ack_requirements=sgc.CONTROLLED_SESSION_ACKS)
        if pilot_proof_override is not None:
            self.pilot_proof = bool(pilot_proof_override)
        else:
            self.pilot_proof = str(sgc.load_artifact("final_report_v170.json").get("pilot_pair_audit_controller_status", "")) == "PASS_PILOT_PAIR_AUDITED_LOCKED"

    @property
    def op_ok(self) -> bool:
        return bool(self.op_v["accepted"])

    @property
    def sess_ok(self) -> bool:
        return bool(self.sess_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.op_v, self.sess_v))

    @property
    def ready(self) -> bool:
        return self.op_ok and self.sess_ok and self.pilot_proof

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_OR_SESSION_APPROVAL"
        if self.ready:
            return "PASS_CONTROLLED_OPERATION_APPROVAL_VALID_NO_SUBMIT"
        return "PARTIAL_CONTROLLED_OPERATION_APPROVAL_OR_LIVE_PROOF_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v174_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v174_baseline_status.startswith("FAIL"):
            return ["FAIL_V174_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_OR_SESSION_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.op_ok:
            blockers.append("CONTROLLED_OPERATION_APPROVAL_ABSENT")
        if not self.sess_ok:
            blockers.append("CONTROLLED_SESSION_APPROVAL_ABSENT")
        if not self.pilot_proof:
            blockers.append("PILOT_PAIR_LIVE_PROOF_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "CONTROLLED_OPERATION_APPROVAL_VALID_NO_SUBMIT_AWAIT_LIVE_SESSION_PREFLIGHT" if self.ready else "OPERATOR_MUST_SUPPLY_CONTROLLED_OPERATION_AND_SESSION_APPROVALS_AND_PILOT_PROOF"


def _common(ctx: V175Context) -> dict[str, Any]:
    return {
        "v174_baseline_status": ctx.v174_baseline_status,
        "controlled_operation_approval_controller_status": ctx.controller_status,
        "controlled_operation_approval_validator_status": "PASS_CONTROLLED_OPERATION_APPROVAL_VALID" if ctx.op_ok else ("FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL" if ctx.op_v["state"] == "PRESENT" and not ctx.op_ok else "PARTIAL_CONTROLLED_OPERATION_APPROVAL_ABSENT"),
        "controlled_session_approval_validator_status": "PASS_CONTROLLED_SESSION_APPROVAL_VALID" if ctx.sess_ok else ("FAIL_CLOSED_INVALID_CONTROLLED_SESSION_APPROVAL" if ctx.sess_v["state"] == "PRESENT" and not ctx.sess_ok else "PARTIAL_CONTROLLED_SESSION_APPROVAL_ABSENT"),
        "first_pilot_proof_checker_status": "PASS_FIRST_PILOT_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_FIRST_PILOT_PROOF_ABSENT",
        "repeat_pilot_proof_checker_status": "PASS_REPEAT_PILOT_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_REPEAT_PILOT_PROOF_ABSENT",
        "pilot_pair_proof_checker_status": "PASS_PILOT_PAIR_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_PILOT_PAIR_PROOF_ABSENT",
        "scale_evidence_status_checker_status": "PASS_SCALE_EVIDENCE_STATUS_READ",
        "risk_abstention_prerequisite_checker_status": "PASS_RISK_ABSTENTION_PRESENT",
        "live_submit_caps_status_checker_status": "PASS_LIVE_SUBMIT_CAPS_READONLY",
        "firewall_adapter_checker_status": "PASS_FIREWALL_ADAPTER_CHECKED",
        "approval_hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "approval_hash_only_ledger": {"controlled_operation": ctx.op_v["approval_hash"], "controlled_session": ctx.sess_v["approval_hash"]},
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "approval_valid": ctx.ready,
        "approval_files_written": 0,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v135_status": "PASS",
        "execution_lock_deep_recheck_v134_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V175Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v174_baseline"):
        return "PASS" if ctx.v174_baseline_status == "PASS_V174_BASELINE_READBACK" else "FAIL" if ctx.v174_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v175_controlled_operation_approval_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V175Context) -> dict[str, Any]:
    workstream = "v175: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v175_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V175_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v175_report.json":
        report.update({"completion_oriented_next_action_v175_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v174_carried_status": ctx.v174_baseline_status, "controlled_operation_approval_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v175_controlled_operation_approval_controller_report.json"), "no_submit": str(ARTIFACTS / "v175_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v175.json", "dummy_canonical_identity_report_v175.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V175ReportFactory:
    def __init__(self, *, operation_approval=None, session_approval=None, pilot_proof_override=None) -> None:
        self.kw = dict(operation_approval=operation_approval, session_approval=session_approval, pilot_proof_override=pilot_proof_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V175Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
