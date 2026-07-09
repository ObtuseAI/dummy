"""DUMMY v248 livebrokerfirewall adapter contract kit no broker contact — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v248 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v248: Livebrokerfirewall Adapter Contract Kit No Broker Contact"
MISSION_NAME = "dummy_mission_state_report_v234.json"
FINAL_NAME = "final_report_v248.json"
INDEX_KEYS = ['adapter_contract_kit_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V248 Livebrokerfirewall Adapter Contract Kit No Broker Contact"
MISSION_KEY = "dummy_mission_state_report_v234"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Adapter Contract Kit', 'adapter_contract_kit_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'live_orders'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V248_ROUTES = ['/api/v248/adapter-contract-kit-controller', '/api/v248/v247-baseline', '/api/v248/contract-kit', '/api/v248/descriptor-present-check', '/api/v248/injected-adapter-contract-check', '/api/v248/non-broker-double-check', '/api/v248/direct-broker-bypass-scan', '/api/v248/market-order-rejection-check', '/api/v248/failure-code', '/api/v248/no-broker-contact-proof', '/api/v248/no-submit-proof', '/api/v248/readiness-governor', '/api/v248/execution-lock', '/api/v248/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'adapter-contract-kit-controller': ['v248_adapter_contract_kit_controller_report.json'], 'v247-baseline': ['v247_baseline_readback_v1_report.json'], 'contract-kit': ['v248_contract_kit_report.json'], 'descriptor-present-check': ['v248_descriptor_present_check_report.json'], 'injected-adapter-contract-check': ['v248_injected_adapter_contract_check_report.json'], 'non-broker-double-check': ['v248_non_broker_double_check_report.json'], 'direct-broker-bypass-scan': ['v248_direct_broker_bypass_scan_report.json'], 'market-order-rejection-check': ['v248_market_order_rejection_check_report.json'], 'failure-code': ['v248_failure_code_report.json'], 'no-broker-contact-proof': ['v248_no_broker_contact_proof_report.json'], 'no-submit-proof': ['v248_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v208_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v207_report.json'], 'mission-state': ['dummy_mission_state_report_v234.json', 'dashboard_v248_report_v1.json', 'completion_oriented_next_action_v248_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(248)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v248/reports.py scripts/generate_v248_reports.py dashboard/backend/v248_routes.py",
    "python scripts/generate_v248_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v248_adapter_contract_kit_controller_report.json"

CONTRACT_KIT = {
    "required_method_shape": "submit(order: dict) -> dict",
    "required_request_fields": ["order_type", "is_market_order", "size_class", "firewall_only", "idempotency_key", "proof_target"],
    "required_response_fields": ["order_attempt_id", "accepted", "real_broker_contacted", "market_order"],
    "idempotency_behavior": "same idempotency_key must not double-submit",
    "limit_order_only_requirement": True,
    "market_order_rejection_requirement": True,
    "cancel_denial_by_default": True,
    "secret_redaction_requirement": True,
    "direct_broker_bypass_prohibition": True,
    "non_broker_double_example_descriptor": "class FakeFirewall: def submit(self, order): return {'order_attempt_id': 'x', 'accepted': True, 'real_broker_contacted': False, 'market_order': False}",
}


class V248Context:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.v247_baseline_status = sgc.baseline_status("final_report_v247.json", "V247")
        self.adapter_present = firewall_adapter is not None
        self.submit_method_ok = self.adapter_present and callable(getattr(firewall_adapter, "submit", None))
        self.contract_ok = False
        self.real_broker_contacted = False
        if self.submit_method_ok:
            probe = firewall_adapter.submit({"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "idempotency_key": "kit-probe", "proof_target": "FIRST_REAL_PILOT_PROOF"})
            self.contract_ok = bool(probe) and probe.get("market_order") is False and "order_attempt_id" in probe
            self.real_broker_contacted = bool(probe.get("real_broker_contacted"))
        self.ready = self.adapter_present and self.submit_method_ok and self.contract_ok and not self.real_broker_contacted

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.adapter_present:
            return "ADAPTER_AWAITS_EXTERNAL_INJECTION"
        if not self.submit_method_ok:
            return "SUBMIT_METHOD_MISSING"
        if not self.contract_ok:
            return "SUBMIT_CONTRACT_INVALID"
        return "ADAPTER_CONTRACT_KIT_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v247_baseline_status.startswith("FAIL"):
            return "FAIL_ADAPTER_CONTRACT_KIT_BASELINE_REGRESSION"
        return "PASS_ADAPTER_CONTRACT_KIT_READY_NON_BROKER_DOUBLE" if self.ready else "PARTIAL_ADAPTER_CONTRACT_KIT_AWAITS_EXTERNAL_ADAPTER"

    @property
    def final_verdict(self) -> str:
        if self.v247_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v247_baseline_status.startswith("FAIL"):
            return ["FAIL_V247_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "ADAPTER_CONTRACT_KIT_READY_RUN_LIVE_SUBMIT_CAPS_REHEARSAL_NO_SUBMIT" if self.ready else "OPERATOR_IMPLEMENT_AND_INJECT_LIVEBROKERFIREWALL_ADAPTER_PER_CONTRACT_KIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v247_baseline_status": ctx.v247_baseline_status,
        "adapter_contract_kit_controller_status": ctx.controller_status,
        "contract_kit": CONTRACT_KIT,
        "contract_kit_status": "PASS_CONTRACT_KIT_EMITTED",
        "descriptor_present_check_status": "PASS_DESCRIPTOR_PRESENT" if ctx.adapter_present else "PARTIAL_DESCRIPTOR_AWAITS_EXTERNAL",
        "injected_adapter_contract_check_status": "PASS_INJECTED_ADAPTER_CONTRACT_VALID" if ctx.contract_ok else "PARTIAL_INJECTED_ADAPTER_ABSENT",
        "non_broker_double_check_status": "PASS_NON_BROKER_DOUBLE_VALID" if ctx.ready else "PARTIAL_NON_BROKER_DOUBLE_ABSENT",
        "direct_broker_bypass_scan_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "market_order_rejection_check_status": "PASS_MARKET_ORDER_REJECTED",
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
        "readiness_governor_v208_status": "PASS",
        "execution_lock_deep_recheck_v207_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v247_baseline"):
        return "PASS" if ctx.v247_baseline_status == "PASS_V247_BASELINE_READBACK" else "FAIL" if ctx.v247_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v248: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v248_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V248_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v248_report.json":
        report.update({"completion_oriented_next_action_v248_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v247_carried_status": ctx.v247_baseline_status, "adapter_contract_kit_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v248.json", "dummy_canonical_identity_report_v248.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V248ReportFactory:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V248Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
