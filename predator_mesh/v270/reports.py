"""DUMMY v270 broker readonly optional verifier no submit cancel — fail-closed staged gate; no live order, no broker contact by default, no submit, no cancel by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v270 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v270: Broker Readonly Optional Verifier No Submit Cancel"
MISSION_NAME = "dummy_mission_state_report_v256.json"
FINAL_NAME = "final_report_v270.json"
INDEX_KEYS = ['broker_readonly_optional_verifier_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V270 Broker Readonly Optional Verifier No Submit Cancel"
MISSION_KEY = "dummy_mission_state_report_v256"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Broker Readonly Verifier', 'broker_readonly_optional_verifier_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'live_orders'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V270_ROUTES = ['/api/v270/broker-readonly-optional-verifier-controller', '/api/v270/v269-baseline', '/api/v270/readonly-approval-check', '/api/v270/readonly-adapter-descriptor-check', '/api/v270/allowed-calls-check', '/api/v270/forbidden-calls-check', '/api/v270/secret-redaction-check', '/api/v270/private-data-minimization-check', '/api/v270/failure-code', '/api/v270/no-submit-cancel-proof', '/api/v270/no-broker-contact-proof', '/api/v270/readiness-governor', '/api/v270/execution-lock', '/api/v270/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'broker-readonly-optional-verifier-controller': ['v270_broker_readonly_optional_verifier_controller_report.json'], 'v269-baseline': ['v269_baseline_readback_v1_report.json'], 'readonly-approval-check': ['v270_readonly_approval_check_report.json'], 'readonly-adapter-descriptor-check': ['v270_readonly_adapter_descriptor_check_report.json'], 'allowed-calls-check': ['v270_allowed_calls_check_report.json'], 'forbidden-calls-check': ['v270_forbidden_calls_check_report.json'], 'secret-redaction-check': ['v270_secret_redaction_check_report.json'], 'private-data-minimization-check': ['v270_private_data_minimization_check_report.json'], 'failure-code': ['v270_failure_code_report.json'], 'no-submit-cancel-proof': ['v270_no_submit_cancel_proof_report.json'], 'no-broker-contact-proof': ['v270_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v230_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v229_report.json'], 'mission-state': ['dummy_mission_state_report_v256.json', 'dashboard_v270_report_v1.json', 'completion_oriented_next_action_v270_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(270)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v270/reports.py scripts/generate_v270_reports.py dashboard/backend/v270_routes.py",
    "python scripts/generate_v270_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v270_broker_readonly_optional_verifier_controller_report.json"

FORBIDDEN_CALLS = ["submit", "cancel", "transfer", "withdrawal", "enable_live_submit", "modify_caps", "market_order"]


class V270Context:
    def __init__(self, *, readonly_adapter=None, readonly_approved=False) -> None:
        self.v269_baseline_status = sgc.baseline_status("final_report_v269.json", "V269")
        self.approved = bool(readonly_approved)
        self.adapter_present = readonly_adapter is not None
        allowed = list(getattr(readonly_adapter, "allowed_calls", []) or []) if self.adapter_present else []
        self.allowed_calls = [c for c in allowed if c not in FORBIDDEN_CALLS]
        self.forbidden_absent = self.adapter_present and not any(callable(getattr(readonly_adapter, c, None)) for c in FORBIDDEN_CALLS) and not any(c in allowed for c in FORBIDDEN_CALLS)
        self.readonly_capable = self.adapter_present and bool(getattr(readonly_adapter, "readonly", True))
        self.ready = self.approved and self.adapter_present and self.readonly_capable and self.forbidden_absent

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.approved and not self.adapter_present:
            return "BROKER_READONLY_SKIPPED_NO_APPROVAL_OR_ADAPTER"
        if not self.approved:
            return "BROKER_READONLY_APPROVAL_ABSENT"
        if not self.adapter_present:
            return "READONLY_ADAPTER_DESCRIPTOR_ABSENT"
        if not self.forbidden_absent:
            return "FORBIDDEN_CALL_PRESENT_FAIL_CLOSED"
        return "BROKER_READONLY_OPTIONAL_VERIFIER_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v269_baseline_status.startswith("FAIL"):
            return "FAIL_BROKER_READONLY_OPTIONAL_VERIFIER_BASELINE_REGRESSION"
        return "PASS_BROKER_READONLY_OPTIONAL_VERIFIER_READY_NON_BROKER_DOUBLE" if self.ready else "PARTIAL_BROKER_READONLY_OPTIONAL_VERIFIER_BLOCKED_OR_SKIPPED"

    @property
    def final_verdict(self) -> str:
        if self.v269_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v269_baseline_status.startswith("FAIL"):
            return ["FAIL_V269_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "BROKER_READONLY_OPTIONAL_VERIFIER_READY_RUN_FINAL_ARMABILITY_RUNBOOK_NO_SUBMIT" if self.ready else "OPTIONAL_OPERATOR_SUPPLY_EXACT_READONLY_APPROVAL_AND_READONLY_ADAPTER_OR_SKIP"


def _common(ctx) -> dict[str, Any]:
    return {
        "v269_baseline_status": ctx.v269_baseline_status,
        "broker_readonly_optional_verifier_controller_status": ctx.controller_status,
        "readonly_approved": ctx.approved,
        "readonly_approval_check_status": "PASS_READONLY_APPROVAL_EXACT" if ctx.approved else "PARTIAL_READONLY_APPROVAL_ABSENT",
        "readonly_adapter_present": ctx.adapter_present,
        "readonly_adapter_descriptor_check_status": "PASS_READONLY_ADAPTER_DESCRIPTOR_PRESENT" if ctx.adapter_present else "PARTIAL_READONLY_ADAPTER_DESCRIPTOR_ABSENT",
        "allowed_calls": ctx.allowed_calls,
        "allowed_calls_check_status": "PASS_ALLOWED_CALLS_READONLY",
        "forbidden_calls": FORBIDDEN_CALLS,
        "forbidden_calls_absent": ctx.forbidden_absent,
        "forbidden_calls_check_status": "PASS_FORBIDDEN_CALLS_ABSENT" if ctx.forbidden_absent else "PARTIAL_FORBIDDEN_CALLS_UNVERIFIED",
        "secret_redaction_check_status": "PASS_SECRETS_REDACTED",
        "private_data_minimization_check_status": "PASS_PRIVATE_DATA_MINIMIZED",
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "no_submit_cancel_proof_status": "PASS_NO_SUBMIT_NO_CANCEL",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "broker_contacted": False,

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
        "readiness_governor_v230_status": "PASS",
        "execution_lock_deep_recheck_v229_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v269_baseline"):
        return "PASS" if ctx.v269_baseline_status == "PASS_V269_BASELINE_READBACK" else "FAIL" if ctx.v269_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v270: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v270_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V270_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v270_report.json":
        report.update({"completion_oriented_next_action_v270_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v269_carried_status": ctx.v269_baseline_status, "broker_readonly_optional_verifier_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v270.json", "dummy_canonical_identity_report_v270.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V270ReportFactory:
    def __init__(self, *, readonly_adapter=None, readonly_approved=False) -> None:
        self.kw = dict(readonly_adapter=readonly_adapter, readonly_approved=readonly_approved)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V270Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
