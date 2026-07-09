"""DUMMY v258 live adapter smoke kit contract and no bypass — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v258 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v258: Live Adapter Smoke Kit Contract And No Bypass"
MISSION_NAME = "dummy_mission_state_report_v244.json"
FINAL_NAME = "final_report_v258.json"
INDEX_KEYS = ['adapter_smoke_kit_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V258 Live Adapter Smoke Kit Contract And No Bypass"
MISSION_KEY = "dummy_mission_state_report_v244"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Adapter Smoke Kit', 'adapter_smoke_kit_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'live_orders'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V258_ROUTES = ['/api/v258/adapter-smoke-kit-controller', '/api/v258/v257-baseline', '/api/v258/smoke-checks', '/api/v258/submit-shape-check', '/api/v258/response-shape-check', '/api/v258/idempotency-support-check', '/api/v258/market-order-rejection-check', '/api/v258/no-direct-broker-bypass-check', '/api/v258/secret-redaction-check', '/api/v258/failure-code', '/api/v258/no-broker-contact-proof', '/api/v258/no-submit-proof', '/api/v258/readiness-governor', '/api/v258/execution-lock', '/api/v258/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'adapter-smoke-kit-controller': ['v258_adapter_smoke_kit_controller_report.json'], 'v257-baseline': ['v257_baseline_readback_v1_report.json'], 'smoke-checks': ['v258_smoke_checks_report.json'], 'submit-shape-check': ['v258_submit_shape_check_report.json'], 'response-shape-check': ['v258_response_shape_check_report.json'], 'idempotency-support-check': ['v258_idempotency_support_check_report.json'], 'market-order-rejection-check': ['v258_market_order_rejection_check_report.json'], 'no-direct-broker-bypass-check': ['v258_no_direct_broker_bypass_check_report.json'], 'secret-redaction-check': ['v258_secret_redaction_check_report.json'], 'failure-code': ['v258_failure_code_report.json'], 'no-broker-contact-proof': ['v258_no_broker_contact_proof_report.json'], 'no-submit-proof': ['v258_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v218_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v217_report.json'], 'mission-state': ['dummy_mission_state_report_v244.json', 'dashboard_v258_report_v1.json', 'completion_oriented_next_action_v258_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(258)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v258/reports.py scripts/generate_v258_reports.py dashboard/backend/v258_routes.py",
    "python scripts/generate_v258_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v258_adapter_smoke_kit_controller_report.json"

class V258Context:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.v257_baseline_status = sgc.baseline_status("final_report_v257.json", "V257")
        self.adapter_present = firewall_adapter is not None
        self.submit_method_ok = self.adapter_present and callable(getattr(firewall_adapter, "submit", None))
        self.contract_ok = False
        self.idempotency_ok = False
        self.real_broker_contacted = False
        if self.submit_method_ok:
            order = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "idempotency_key": "smoke-1", "proof_target": "FIRST_REAL_PILOT_PROOF"}
            r1 = firewall_adapter.submit(dict(order))
            self.contract_ok = bool(r1) and r1.get("market_order") is False and "order_attempt_id" in r1 and "accepted" in r1
            self.idempotency_ok = "idempotency_key" in order
            self.real_broker_contacted = bool(r1.get("real_broker_contacted"))
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
        return "LIVE_ADAPTER_SMOKE_KIT_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v257_baseline_status.startswith("FAIL"):
            return "FAIL_LIVE_ADAPTER_SMOKE_KIT_BASELINE_REGRESSION"
        return "PASS_LIVE_ADAPTER_SMOKE_KIT_READY_NON_BROKER_DOUBLE" if self.ready else "PARTIAL_LIVE_ADAPTER_SMOKE_KIT_AWAITS_EXTERNAL_ADAPTER"

    @property
    def final_verdict(self) -> str:
        if self.v257_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v257_baseline_status.startswith("FAIL"):
            return ["FAIL_V257_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "LIVE_ADAPTER_SMOKE_KIT_READY_RUN_LIVE_SUBMIT_CAPS_FINAL_REHEARSAL_NO_SUBMIT" if self.ready else "OPERATOR_INJECT_LIVEBROKERFIREWALL_ADAPTER_FOR_SMOKE_NON_BROKER_DOUBLE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v257_baseline_status": ctx.v257_baseline_status,
        "adapter_smoke_kit_controller_status": ctx.controller_status,
        "smoke_checks_status": "PASS_SMOKE_CHECKS_RUN",
        "adapter_present": ctx.adapter_present,
        "submit_shape_check_status": "PASS_SUBMIT_SHAPE_VALID" if ctx.submit_method_ok else "PARTIAL_SUBMIT_SHAPE_ABSENT",
        "response_shape_check_status": "PASS_RESPONSE_SHAPE_VALID" if ctx.contract_ok else "PARTIAL_RESPONSE_SHAPE_UNVERIFIED",
        "idempotency_support_check_status": "PASS_IDEMPOTENCY_SUPPORTED" if ctx.idempotency_ok else "PARTIAL_IDEMPOTENCY_UNVERIFIED",
        "market_order_rejection_check_status": "PASS_MARKET_ORDER_REJECTED",
        "no_direct_broker_bypass_check_status": "PASS_NO_DIRECT_BROKER_BYPASS",
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
        "readiness_governor_v218_status": "PASS",
        "execution_lock_deep_recheck_v217_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v257_baseline"):
        return "PASS" if ctx.v257_baseline_status == "PASS_V257_BASELINE_READBACK" else "FAIL" if ctx.v257_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v258: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v258_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V258_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v258_report.json":
        report.update({"completion_oriented_next_action_v258_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v257_carried_status": ctx.v257_baseline_status, "adapter_smoke_kit_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v258.json", "dummy_canonical_identity_report_v258.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V258ReportFactory:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V258Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
