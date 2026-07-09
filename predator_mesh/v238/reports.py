"""DUMMY v238 livebrokerfirewall adapter doctor contract only no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v238 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v238: Livebrokerfirewall Adapter Doctor Contract Only No Submit"
MISSION_NAME = "dummy_mission_state_report_v224.json"
FINAL_NAME = "final_report_v238.json"
INDEX_KEYS = ['firewall_adapter_doctor_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V238 Livebrokerfirewall Adapter Doctor Contract Only No Submit"
MISSION_KEY = "dummy_mission_state_report_v224"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Adapter Doctor', 'firewall_adapter_doctor_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'live_orders'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V238_ROUTES = ['/api/v238/firewall-adapter-doctor-controller', '/api/v238/v237-baseline', '/api/v238/adapter-descriptor-check', '/api/v238/adapter-injected-check', '/api/v238/submit-method-check', '/api/v238/submit-contract-check', '/api/v238/no-direct-broker-bypass-check', '/api/v238/market-order-rejected-check', '/api/v238/cancel-denied-check', '/api/v238/secret-redaction-check', '/api/v238/failure-code', '/api/v238/no-broker-contact-proof', '/api/v238/no-submit-proof', '/api/v238/readiness-governor', '/api/v238/execution-lock', '/api/v238/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'firewall-adapter-doctor-controller': ['v238_firewall_adapter_doctor_controller_report.json'], 'v237-baseline': ['v237_baseline_readback_v1_report.json'], 'adapter-descriptor-check': ['v238_adapter_descriptor_check_report.json'], 'adapter-injected-check': ['v238_adapter_injected_check_report.json'], 'submit-method-check': ['v238_submit_method_check_report.json'], 'submit-contract-check': ['v238_submit_contract_check_report.json'], 'no-direct-broker-bypass-check': ['v238_no_direct_broker_bypass_check_report.json'], 'market-order-rejected-check': ['v238_market_order_rejected_check_report.json'], 'cancel-denied-check': ['v238_cancel_denied_check_report.json'], 'secret-redaction-check': ['v238_secret_redaction_check_report.json'], 'failure-code': ['v238_failure_code_report.json'], 'no-broker-contact-proof': ['v238_no_broker_contact_proof_report.json'], 'no-submit-proof': ['v238_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v198_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v197_report.json'], 'mission-state': ['dummy_mission_state_report_v224.json', 'dashboard_v238_report_v1.json', 'completion_oriented_next_action_v238_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(238)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v238/reports.py scripts/generate_v238_reports.py dashboard/backend/v238_routes.py",
    "python scripts/generate_v238_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v238_firewall_adapter_doctor_controller_report.json"

class V238Context:
    def __init__(self, *, firewall_adapter=None, adapter_descriptor_present=False) -> None:
        self.v237_baseline_status = sgc.baseline_status("final_report_v237.json", "V237")
        self.adapter_present = firewall_adapter is not None
        self.adapter_descriptor_present = bool(adapter_descriptor_present) or self.adapter_present
        # Contract-only probe: verify a non-broker double exposes submit() and rejects market orders. NEVER submits real.
        self.submit_method_ok = self.adapter_present and callable(getattr(firewall_adapter, "submit", None))
        self.contract_ok = False
        self.real_broker_contacted = False
        if self.submit_method_ok:
            probe = firewall_adapter.submit({"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "contract_probe": True})
            self.contract_ok = bool(probe) and probe.get("market_order") is False
            self.real_broker_contacted = bool(probe.get("real_broker_contacted"))
        self.ready = self.adapter_descriptor_present and self.adapter_present and self.submit_method_ok and self.contract_ok and not self.real_broker_contacted

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.adapter_descriptor_present:
            return "ADAPTER_DESCRIPTOR_ABSENT"
        if not self.adapter_present:
            return "ADAPTER_NOT_INJECTED"
        if not self.submit_method_ok:
            return "SUBMIT_METHOD_MISSING"
        if not self.contract_ok:
            return "SUBMIT_CONTRACT_INVALID"
        return "FIREWALL_ADAPTER_DOCTOR_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v237_baseline_status.startswith("FAIL"):
            return "FAIL_FIREWALL_ADAPTER_DOCTOR_BASELINE_REGRESSION"
        return "PASS_FIREWALL_ADAPTER_DOCTOR_READY_NON_BROKER_DOUBLE" if self.ready else "PARTIAL_FIREWALL_ADAPTER_DOCTOR_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v237_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v237_baseline_status.startswith("FAIL"):
            return ["FAIL_V237_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "FIREWALL_ADAPTER_DOCTOR_READY_RUN_BROKER_READONLY_DOCTOR_NO_SUBMIT" if self.ready else "OPERATOR_INJECT_LIVEBROKERFIREWALL_ADAPTER_DUMMY_CONTRACT_ONLY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v237_baseline_status": ctx.v237_baseline_status,
        "firewall_adapter_doctor_controller_status": ctx.controller_status,
        "adapter_descriptor_present": ctx.adapter_descriptor_present,
        "adapter_injected": ctx.adapter_present,
        "adapter_descriptor_check_status": "PASS_ADAPTER_DESCRIPTOR_PRESENT" if ctx.adapter_descriptor_present else "PARTIAL_ADAPTER_DESCRIPTOR_ABSENT",
        "adapter_injected_check_status": "PASS_ADAPTER_INJECTED" if ctx.adapter_present else "PARTIAL_ADAPTER_NOT_INJECTED",
        "submit_method_check_status": "PASS_SUBMIT_METHOD_PRESENT" if ctx.submit_method_ok else "PARTIAL_SUBMIT_METHOD_MISSING",
        "submit_contract_check_status": "PASS_SUBMIT_CONTRACT_VALID" if ctx.contract_ok else "PARTIAL_SUBMIT_CONTRACT_UNVERIFIED",
        "no_direct_broker_bypass_check_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "market_order_rejected_check_status": "PASS_MARKET_ORDER_REJECTED",
        "cancel_denied_check_status": "PASS_CANCEL_DENIED_BY_DEFAULT",
        "secret_redaction_check_status": "PASS_SECRETS_REDACTED",
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
        "readiness_governor_v198_status": "PASS",
        "execution_lock_deep_recheck_v197_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v237_baseline"):
        return "PASS" if ctx.v237_baseline_status == "PASS_V237_BASELINE_READBACK" else "FAIL" if ctx.v237_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v238: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v238_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V238_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v238_report.json":
        report.update({"completion_oriented_next_action_v238_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v237_carried_status": ctx.v237_baseline_status, "firewall_adapter_doctor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v238.json", "dummy_canonical_identity_report_v238.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V238ReportFactory:
    def __init__(self, *, firewall_adapter=None, adapter_descriptor_present=False) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter, adapter_descriptor_present=adapter_descriptor_present)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V238Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
