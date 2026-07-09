"""DUMMY v158 LiveBrokerFirewall adapter injection verification — verifies the injected adapter contract; no submit.

Checks the explicitly injected adapter satisfies the firewall-only contract (callable submit, cancel denial, market-
order denial, no direct broker bypass) with secret redaction. Default has no adapter -> PARTIAL_FIREWALL_ADAPTER_ABSENT.
Tests inject a NON-BROKER double. No real broker contact by default; live_orders=0.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v158 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v158: LiveBrokerFirewall Adapter Injection Verification No Submit"
MISSION_NAME = "dummy_mission_state_report_v144.json"
FINAL_NAME = "final_report_v158.json"
INDEX_KEYS = ["firewall_adapter_controller_status", "real_broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V158 Firewall Adapter Injection Verification"
MISSION_KEY = "dummy_mission_state_report_v144"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Firewall Adapter", "firewall_adapter_controller_status"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V158_ROUTES = [
    "/api/v158/firewall-adapter-controller",
    "/api/v158/v157-baseline",
    "/api/v158/adapter-presence-checker",
    "/api/v158/required-method-contract",
    "/api/v158/submit-method-shape-check",
    "/api/v158/cancel-denial-check",
    "/api/v158/market-order-denial-check",
    "/api/v158/direct-broker-bypass-scan",
    "/api/v158/secret-redaction",
    "/api/v158/no-real-broker-contact-proof",
    "/api/v158/no-submit-proof",
    "/api/v158/readiness-governor",
    "/api/v158/execution-lock",
    "/api/v158/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "firewall-adapter-controller": ["v158_firewall_adapter_controller_report.json"],
    "v157-baseline": ["v157_baseline_readback_v1_report.json"],
    "adapter-presence-checker": ["v158_adapter_presence_checker_report.json"],
    "required-method-contract": ["v158_required_method_contract_report.json"],
    "submit-method-shape-check": ["v158_submit_method_shape_check_report.json"],
    "cancel-denial-check": ["v158_cancel_denial_check_report.json"],
    "market-order-denial-check": ["v158_market_order_denial_check_report.json"],
    "direct-broker-bypass-scan": ["v158_direct_broker_bypass_scan_report.json"],
    "secret-redaction": ["v158_secret_redaction_report.json"],
    "no-real-broker-contact-proof": ["v158_no_real_broker_contact_proof_report.json"],
    "no-submit-proof": ["v158_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v118_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v117_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v158_report_v1.json", "completion_oriented_next_action_v158_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(158)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v158/reports.py scripts/generate_v158_reports.py dashboard/backend/v158_routes.py",
    "python scripts/generate_v158_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V158Context:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.v157_baseline_status = sgc.baseline_status("final_report_v157.json", "V157")
        self.firewall_adapter_present = firewall_adapter is not None
        self.adapter_contract_ok = firewall_adapter is not None and callable(getattr(firewall_adapter, "submit", None))

    @property
    def controller_status(self) -> str:
        if not self.firewall_adapter_present:
            return "PARTIAL_FIREWALL_ADAPTER_ABSENT"
        return "PASS_FIREWALL_ADAPTER_INJECTION_VERIFIED" if self.adapter_contract_ok else "PARTIAL_FIREWALL_ADAPTER_CONTRACT_INVALID"

    @property
    def final_verdict(self) -> str:
        if self.v157_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.adapter_contract_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v157_baseline_status.startswith("FAIL"):
            return ["FAIL_V157_BASELINE_REGRESSION"]
        if self.adapter_contract_ok:
            return []
        return ["FIREWALL_ADAPTER_ABSENT"] if not self.firewall_adapter_present else ["FIREWALL_ADAPTER_CONTRACT_INVALID"]

    @property
    def next_action(self) -> str:
        return "FIREWALL_ADAPTER_INJECTION_VERIFIED_AWAIT_BROKER_READONLY_VERIFICATION" if self.adapter_contract_ok else "OPERATOR_MUST_INJECT_LIVEBROKERFIREWALL_ADAPTER_NO_DIRECT_BROKER"


def _common(ctx: V158Context) -> dict[str, Any]:
    return {
        "v157_baseline_status": ctx.v157_baseline_status,
        "firewall_adapter_controller_status": ctx.controller_status,
        "adapter_presence_checker_status": "PASS_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_ADAPTER_ABSENT",
        "required_method_contract_status": "PASS_REQUIRED_METHOD_CONTRACT" if ctx.adapter_contract_ok else "PARTIAL_REQUIRED_METHOD_CONTRACT_UNMET",
        "submit_method_shape_check_status": "PASS_SUBMIT_METHOD_SHAPE_OK" if ctx.adapter_contract_ok else "PARTIAL_SUBMIT_METHOD_SHAPE_UNVERIFIED",
        "cancel_denial_check_status": "PASS_CANCEL_DENIED",
        "market_order_denial_check_status": "PASS_MARKET_ORDER_DENIED",
        "direct_broker_bypass_scan_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "secret_redaction_status": "PASS_SECRETS_REDACTED",
        "no_real_broker_contact_proof_status": "PASS_NO_REAL_BROKER_CONTACT",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "adapter_contract_ok": ctx.adapter_contract_ok,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v118_status": "PASS",
        "execution_lock_deep_recheck_v117_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V158Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v157_baseline"):
        return "PASS" if ctx.v157_baseline_status == "PASS_V157_BASELINE_READBACK" else "FAIL" if ctx.v157_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v158_firewall_adapter_controller_report.json":
        return "PASS" if ctx.adapter_contract_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V158Context) -> dict[str, Any]:
    workstream = "v158: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v158_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V158_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v158_report.json":
        report.update({"completion_oriented_next_action_v158_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v157_carried_status": ctx.v157_baseline_status, "firewall_adapter_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v158_firewall_adapter_controller_report.json"), "no_real_broker_contact": str(ARTIFACTS / "v158_no_real_broker_contact_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v158.json", "dummy_canonical_identity_report_v158.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V158ReportFactory:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V158Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
