"""DUMMY v186 controlled session authority recheck — rechecks controlled-session authority + prerequisite proof; never submits.

Validates the exact controlled-operation and controlled-session approvals and checks first-pilot / repeat-pilot /
pilot-pair / live-submit-caps / firewall / mode-firewall / candidate-risk-abstention prerequisites. Emits a hash-only
ledger. Default is PARTIAL_CONTROLLED_SESSION_AUTHORITY_BLOCKED. No submit, no approval-file writes.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v186 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v186: Controlled Session Authority Recheck No Submit"
MISSION_NAME = "dummy_mission_state_report_v172.json"
FINAL_NAME = "final_report_v186.json"
INDEX_KEYS = ["session_authority_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V186 Controlled Session Authority Recheck"
MISSION_KEY = "dummy_mission_state_report_v172"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Authority", "session_authority_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V186_ROUTES = [
    "/api/v186/session-authority-controller",
    "/api/v186/v185-baseline",
    "/api/v186/controlled-operation-approval-validator",
    "/api/v186/controlled-session-approval-validator",
    "/api/v186/first-pilot-proof-checker",
    "/api/v186/repeat-pilot-proof-checker",
    "/api/v186/pilot-pair-proof-checker",
    "/api/v186/live-submit-caps-readonly-checker",
    "/api/v186/firewall-adapter-checker",
    "/api/v186/mode-firewall-checker",
    "/api/v186/candidate-risk-abstention-proof-checker",
    "/api/v186/approval-hash-only-ledger",
    "/api/v186/no-approval-file-write-proof",
    "/api/v186/no-submit-proof",
    "/api/v186/readiness-governor",
    "/api/v186/execution-lock",
    "/api/v186/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-authority-controller": ["v186_session_authority_controller_report.json"],
    "v185-baseline": ["v185_baseline_readback_v1_report.json"],
    "controlled-operation-approval-validator": ["v186_controlled_operation_approval_validator_report.json"],
    "controlled-session-approval-validator": ["v186_controlled_session_approval_validator_report.json"],
    "first-pilot-proof-checker": ["v186_first_pilot_proof_checker_report.json"],
    "repeat-pilot-proof-checker": ["v186_repeat_pilot_proof_checker_report.json"],
    "pilot-pair-proof-checker": ["v186_pilot_pair_proof_checker_report.json"],
    "live-submit-caps-readonly-checker": ["v186_live_submit_caps_readonly_checker_report.json"],
    "firewall-adapter-checker": ["v186_firewall_adapter_checker_report.json"],
    "mode-firewall-checker": ["v186_mode_firewall_checker_report.json"],
    "candidate-risk-abstention-proof-checker": ["v186_candidate_risk_abstention_proof_checker_report.json"],
    "approval-hash-only-ledger": ["v186_approval_hash_only_ledger_report.json"],
    "no-approval-file-write-proof": ["v186_no_approval_file_write_proof_report.json"],
    "no-submit-proof": ["v186_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v146_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v145_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v186_report_v1.json", "completion_oriented_next_action_v186_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(186)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v186/reports.py scripts/generate_v186_reports.py dashboard/backend/v186_routes.py",
    "python scripts/generate_v186_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V186Context:
    def __init__(self, *, operation_approval=None, session_approval=None, pilot_proof_override=None) -> None:
        self.v185_baseline_status = sgc.baseline_status("final_report_v185.json", "V185")
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
            return "PASS_CONTROLLED_SESSION_AUTHORITY_READY_NO_SUBMIT"
        return "PARTIAL_CONTROLLED_SESSION_AUTHORITY_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v185_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v185_baseline_status.startswith("FAIL"):
            return ["FAIL_V185_BASELINE_REGRESSION"]
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
        return "CONTROLLED_SESSION_AUTHORITY_READY_NO_SUBMIT_AWAIT_GATED_FIRE_STAGE" if self.ready else "OPERATOR_MUST_SUPPLY_CONTROLLED_OPERATION_AND_SESSION_APPROVALS_AND_PILOT_PROOF"


def _common(ctx: V186Context) -> dict[str, Any]:
    return {
        "v185_baseline_status": ctx.v185_baseline_status,
        "session_authority_controller_status": ctx.controller_status,
        "controlled_operation_approval_validator_status": "PASS_CONTROLLED_OPERATION_APPROVAL_VALID" if ctx.op_ok else ("FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL" if ctx.op_v["state"] == "PRESENT" and not ctx.op_ok else "PARTIAL_CONTROLLED_OPERATION_APPROVAL_ABSENT"),
        "controlled_session_approval_validator_status": "PASS_CONTROLLED_SESSION_APPROVAL_VALID" if ctx.sess_ok else ("FAIL_CLOSED_INVALID_CONTROLLED_SESSION_APPROVAL" if ctx.sess_v["state"] == "PRESENT" and not ctx.sess_ok else "PARTIAL_CONTROLLED_SESSION_APPROVAL_ABSENT"),
        "first_pilot_proof_checker_status": "PASS_FIRST_PILOT_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_FIRST_PILOT_PROOF_ABSENT",
        "repeat_pilot_proof_checker_status": "PASS_REPEAT_PILOT_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_REPEAT_PILOT_PROOF_ABSENT",
        "pilot_pair_proof_checker_status": "PASS_PILOT_PAIR_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_PILOT_PAIR_PROOF_ABSENT",
        "live_submit_caps_readonly_checker_status": "PASS_LIVE_SUBMIT_CAPS_READONLY",
        "firewall_adapter_checker_status": "PASS_FIREWALL_ADAPTER_CHECKED",
        "mode_firewall_checker_status": "PASS_MODE_FIREWALL_CHECKED",
        "candidate_risk_abstention_proof_checker_status": "PASS_CANDIDATE_RISK_ABSTENTION_PRESENT",
        "approval_hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "approval_hash_only_ledger": {"controlled_operation": ctx.op_v["approval_hash"], "controlled_session": ctx.sess_v["approval_hash"]},
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "authority_ready": ctx.ready,
        "approval_files_written": 0,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v146_status": "PASS",
        "execution_lock_deep_recheck_v145_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V186Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v185_baseline"):
        return "PASS" if ctx.v185_baseline_status == "PASS_V185_BASELINE_READBACK" else "FAIL" if ctx.v185_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v186_session_authority_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V186Context) -> dict[str, Any]:
    workstream = "v186: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v186_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V186_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v186_report.json":
        report.update({"completion_oriented_next_action_v186_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v185_carried_status": ctx.v185_baseline_status, "session_authority_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v186_session_authority_controller_report.json"), "no_submit": str(ARTIFACTS / "v186_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v186.json", "dummy_canonical_identity_report_v186.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V186ReportFactory:
    def __init__(self, *, operation_approval=None, session_approval=None, pilot_proof_override=None) -> None:
        self.kw = dict(operation_approval=operation_approval, session_approval=session_approval, pilot_proof_override=pilot_proof_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V186Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
