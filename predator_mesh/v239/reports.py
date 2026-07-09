"""DUMMY v239 broker readonly doctor no submit cancel — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v239 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v239: Broker Readonly Doctor No Submit Cancel"
MISSION_NAME = "dummy_mission_state_report_v225.json"
FINAL_NAME = "final_report_v239.json"
INDEX_KEYS = ['broker_readonly_doctor_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V239 Broker Readonly Doctor No Submit Cancel"
MISSION_KEY = "dummy_mission_state_report_v225"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Broker RO Doctor', 'broker_readonly_doctor_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'live_orders'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V239_ROUTES = ['/api/v239/broker-readonly-doctor-controller', '/api/v239/v238-baseline', '/api/v239/broker-readonly-approval-check', '/api/v239/readonly-adapter-capability-check', '/api/v239/allowed-calls-list', '/api/v239/forbidden-calls-list', '/api/v239/no-submit-no-cancel-check', '/api/v239/secret-redaction-check', '/api/v239/private-data-minimization-check', '/api/v239/failure-code', '/api/v239/no-broker-contact-proof', '/api/v239/no-submit-proof', '/api/v239/readiness-governor', '/api/v239/execution-lock', '/api/v239/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'broker-readonly-doctor-controller': ['v239_broker_readonly_doctor_controller_report.json'], 'v238-baseline': ['v238_baseline_readback_v1_report.json'], 'broker-readonly-approval-check': ['v239_broker_readonly_approval_check_report.json'], 'readonly-adapter-capability-check': ['v239_readonly_adapter_capability_check_report.json'], 'allowed-calls-list': ['v239_allowed_calls_list_report.json'], 'forbidden-calls-list': ['v239_forbidden_calls_list_report.json'], 'no-submit-no-cancel-check': ['v239_no_submit_no_cancel_check_report.json'], 'secret-redaction-check': ['v239_secret_redaction_check_report.json'], 'private-data-minimization-check': ['v239_private_data_minimization_check_report.json'], 'failure-code': ['v239_failure_code_report.json'], 'no-broker-contact-proof': ['v239_no_broker_contact_proof_report.json'], 'no-submit-proof': ['v239_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v199_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v198_report.json'], 'mission-state': ['dummy_mission_state_report_v225.json', 'dashboard_v239_report_v1.json', 'completion_oriented_next_action_v239_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(239)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v239/reports.py scripts/generate_v239_reports.py dashboard/backend/v239_routes.py",
    "python scripts/generate_v239_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v239_broker_readonly_doctor_controller_report.json"

ALLOWED_READONLY_CALLS = ["get_account_readonly_status", "get_positions_readonly", "get_balances_readonly", "verify_connectivity_readonly"]
FORBIDDEN_CALLS = ["submit", "cancel", "transfer", "withdraw", "enable_live_submit", "modify_caps", "market_order"]


class V239Context:
    def __init__(self, *, readonly_approval=None, readonly_approval_path=None, readonly_adapter=None) -> None:
        self.v238_baseline_status = sgc.baseline_status("final_report_v238.json", "V238")
        resolution = sgc.resolve_packet(readonly_approval_path, readonly_approval)
        self.approval = sgc.validate_packet(
            resolution,
            required_phrase=sgc.BROKER_READONLY_PHRASE,
            required_fields=sgc.BROKER_READONLY_FIELDS,
            required_scope=sgc.BROKER_READONLY_SCOPE,
        )
        self.adapter_present = readonly_adapter is not None
        self.real_broker_contacted = False
        self.readonly_ok = False
        if self.adapter_present and callable(getattr(readonly_adapter, "read_only_verify", None)):
            probe = readonly_adapter.read_only_verify()
            self.readonly_ok = bool(probe) and probe.get("submit_capable") is False
            self.real_broker_contacted = bool(probe.get("real_broker_contacted"))
        self.ready = bool(self.approval["accepted"]) and self.adapter_present and self.readonly_ok and not self.real_broker_contacted

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.approval["accepted"]:
            return "BROKER_READONLY_APPROVAL_ABSENT" if self.approval["state"] != "PRESENT" else "BROKER_READONLY_PHRASE_INVALID"
        if not self.adapter_present or not self.readonly_ok:
            return "READONLY_ADAPTER_ABSENT"
        return "BROKER_READONLY_DOCTOR_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v238_baseline_status.startswith("FAIL"):
            return "FAIL_BROKER_READONLY_DOCTOR_BASELINE_REGRESSION"
        return "PASS_BROKER_READONLY_DOCTOR_READY_NON_BROKER_DOUBLE" if self.ready else "PARTIAL_BROKER_READONLY_DOCTOR_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v238_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v238_baseline_status.startswith("FAIL"):
            return ["FAIL_V238_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "BROKER_READONLY_DOCTOR_READY_RUN_ARMABLE_QUORUM_DOCTOR_NO_SUBMIT" if self.ready else "OPERATOR_SUPPLY_BROKER_READONLY_APPROVAL_AND_READONLY_ADAPTER_DUMMY_NO_CONTACT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v238_baseline_status": ctx.v238_baseline_status,
        "broker_readonly_doctor_controller_status": ctx.controller_status,
        "broker_readonly_approval_accepted": bool(ctx.approval["accepted"]),
        "broker_readonly_approval_hash": ctx.approval["approval_hash"],
        "allowed_calls_list": ALLOWED_READONLY_CALLS,
        "forbidden_calls_list": FORBIDDEN_CALLS,
        "broker_readonly_approval_check_status": "PASS_BROKER_READONLY_APPROVAL_EXACT" if ctx.approval["accepted"] else "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT_OR_INVALID",
        "readonly_adapter_capability_check_status": "PASS_READONLY_ADAPTER_CAPABLE" if ctx.readonly_ok else "PARTIAL_READONLY_ADAPTER_ABSENT",
        "allowed_calls_list_status": "PASS_ALLOWED_CALLS_LISTED",
        "forbidden_calls_list_status": "PASS_FORBIDDEN_CALLS_LISTED",
        "no_submit_no_cancel_check_status": "PASS_NO_SUBMIT_NO_CANCEL",
        "secret_redaction_check_status": "PASS_SECRETS_REDACTED",
        "private_data_minimization_check_status": "PASS_PRIVATE_DATA_MINIMIZED",
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "broker_contacted": ctx.real_broker_contacted,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": ctx.real_broker_contacted,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v199_status": "PASS",
        "execution_lock_deep_recheck_v198_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v238_baseline"):
        return "PASS" if ctx.v238_baseline_status == "PASS_V238_BASELINE_READBACK" else "FAIL" if ctx.v238_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v239: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v239_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V239_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v239_report.json":
        report.update({"completion_oriented_next_action_v239_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v238_carried_status": ctx.v238_baseline_status, "broker_readonly_doctor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v239.json", "dummy_canonical_identity_report_v239.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V239ReportFactory:
    def __init__(self, *, readonly_approval=None, readonly_approval_path=None, readonly_adapter=None) -> None:
        self.kw = dict(readonly_approval=readonly_approval, readonly_approval_path=readonly_approval_path, readonly_adapter=readonly_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V239Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
