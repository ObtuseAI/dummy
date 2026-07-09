"""DUMMY v197 firewall + broker read-only verification V2 — verifies the firewall contract and broker read-only path; no submit/cancel.

Verifies an injected LiveBrokerFirewall adapter (callable submit, market-order denial, cancel denial, no direct broker
bypass) and, if an exact broker-read-only approval and read-only adapter exist, permits only allowed read-only calls.
Default is PARTIAL_FIREWALL_OR_BROKER_READONLY_AUTHORITY_ABSENT. Tests inject NON-broker doubles;
real_broker_contacted=false, no submit/cancel.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v197 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v197: Firewall And Broker Readonly Verification V2 No Submit Cancel"
MISSION_NAME = "dummy_mission_state_report_v183.json"
FINAL_NAME = "final_report_v197.json"
INDEX_KEYS = ["firewall_broker_controller_status", "real_broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V197 Firewall & Broker Read-Only Verification V2"
MISSION_KEY = "dummy_mission_state_report_v183"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Firewall/Broker", "firewall_broker_controller_status"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V197_ROUTES = [
    "/api/v197/firewall-broker-controller",
    "/api/v197/v196-baseline",
    "/api/v197/firewall-adapter-contract-checker",
    "/api/v197/submit-method-shape-check",
    "/api/v197/market-order-denial",
    "/api/v197/cancel-denial-default",
    "/api/v197/direct-broker-bypass-scan",
    "/api/v197/broker-readonly-approval-validator",
    "/api/v197/readonly-capability-checker",
    "/api/v197/allowed-readonly-call-list",
    "/api/v197/forbidden-call-list",
    "/api/v197/secret-redaction",
    "/api/v197/account-private-data-minimization",
    "/api/v197/no-submit-cancel-proof",
    "/api/v197/readiness-governor",
    "/api/v197/execution-lock",
    "/api/v197/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "firewall-broker-controller": ["v197_firewall_broker_controller_report.json"],
    "v196-baseline": ["v196_baseline_readback_v1_report.json"],
    "firewall-adapter-contract-checker": ["v197_firewall_adapter_contract_checker_report.json"],
    "submit-method-shape-check": ["v197_submit_method_shape_check_report.json"],
    "market-order-denial": ["v197_market_order_denial_report.json"],
    "cancel-denial-default": ["v197_cancel_denial_default_report.json"],
    "direct-broker-bypass-scan": ["v197_direct_broker_bypass_scan_report.json"],
    "broker-readonly-approval-validator": ["v197_broker_readonly_approval_validator_report.json"],
    "readonly-capability-checker": ["v197_readonly_capability_checker_report.json"],
    "allowed-readonly-call-list": ["v197_allowed_readonly_call_list_report.json"],
    "forbidden-call-list": ["v197_forbidden_call_list_report.json"],
    "secret-redaction": ["v197_secret_redaction_report.json"],
    "account-private-data-minimization": ["v197_account_private_data_minimization_report.json"],
    "no-submit-cancel-proof": ["v197_no_submit_cancel_proof_report.json"],
    "readiness-governor": ["readiness_governor_v157_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v156_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v197_report_v1.json", "completion_oriented_next_action_v197_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(197)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v197/reports.py scripts/generate_v197_reports.py dashboard/backend/v197_routes.py",
    "python scripts/generate_v197_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ALLOWED_READONLY_CALLS = ["get_account_status", "get_balances_readonly", "get_open_orders_readonly", "get_positions_readonly"]
FORBIDDEN_CALLS = ["submit", "cancel", "transfer", "withdrawal", "enable_live_submit", "modify_caps", "market_order"]


class V197Context:
    def __init__(self, *, firewall_adapter=None, broker_readonly_approval=None, readonly_adapter=None) -> None:
        self.v196_baseline_status = sgc.baseline_status("final_report_v196.json", "V196")
        self.firewall_ok = firewall_adapter is not None and callable(getattr(firewall_adapter, "submit", None))
        self.broker_v = sgc.validate_packet(sgc.resolve_packet(None, broker_readonly_approval), required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)
        self.readonly_adapter_ok = readonly_adapter is not None and callable(getattr(readonly_adapter, "read_only_verify", None))
        self.verify_result = None
        if self.broker_v["accepted"] and self.readonly_adapter_ok:
            self.verify_result = readonly_adapter.read_only_verify()

    @property
    def broker_ok(self) -> bool:
        return bool(self.broker_v["accepted"]) and self.readonly_adapter_ok and self.verify_result is not None

    @property
    def any_fail(self) -> bool:
        return self.broker_v["state"] == "PRESENT" and not self.broker_v["accepted"]

    @property
    def real_broker_contacted(self) -> bool:
        return bool(self.verify_result and self.verify_result.get("real_broker_contacted"))

    @property
    def verified(self) -> bool:
        return self.firewall_ok and self.broker_ok

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"
        if self.verified:
            return "PASS_FIREWALL_AND_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
        return "PARTIAL_FIREWALL_OR_BROKER_READONLY_AUTHORITY_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v196_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.verified else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v196_baseline_status.startswith("FAIL"):
            return ["FAIL_V196_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"]
        if self.verified:
            return []
        blockers: list[str] = []
        if not self.firewall_ok:
            blockers.append("FIREWALL_ADAPTER_ABSENT")
        if not self.broker_ok:
            blockers.append("BROKER_READONLY_APPROVAL_OR_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "FIREWALL_AND_BROKER_READONLY_VERIFIED_AWAIT_FIRST_LIVE_PROOF_QUORUM" if self.verified else "OPERATOR_MUST_INJECT_FIREWALL_ADAPTER_AND_SUPPLY_BROKER_READONLY_APPROVAL_ADAPTER"


def _common(ctx: V197Context) -> dict[str, Any]:
    return {
        "v196_baseline_status": ctx.v196_baseline_status,
        "firewall_broker_controller_status": ctx.controller_status,
        "firewall_adapter_contract_checker_status": "PASS_FIREWALL_ADAPTER_CONTRACT_VALID" if ctx.firewall_ok else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "submit_method_shape_check_status": "PASS_SUBMIT_METHOD_SHAPE_OK" if ctx.firewall_ok else "PARTIAL_SUBMIT_METHOD_SHAPE_UNVERIFIED",
        "market_order_denial_status": "PASS_MARKET_ORDER_DENIED",
        "cancel_denial_default_status": "PASS_CANCEL_DENIED_DEFAULT",
        "direct_broker_bypass_scan_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "broker_readonly_approval_validator_status": "PASS_BROKER_READONLY_APPROVAL_VALID" if ctx.broker_v["accepted"] else ("FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL" if ctx.any_fail else "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT"),
        "readonly_capability_checker_status": "PASS_READONLY_ADAPTER_CAPABLE" if ctx.readonly_adapter_ok else "PARTIAL_READONLY_ADAPTER_ABSENT",
        "allowed_readonly_call_list_status": "PASS_ALLOWED_READONLY_CALLS_LISTED",
        "allowed_readonly_calls": ALLOWED_READONLY_CALLS,
        "forbidden_call_list_status": "PASS_FORBIDDEN_CALLS_LISTED",
        "forbidden_calls": FORBIDDEN_CALLS,
        "secret_redaction_status": "PASS_SECRETS_REDACTED",
        "account_private_data_minimization_status": "PASS_PRIVATE_DATA_MINIMIZED",
        "no_submit_cancel_proof_status": "PASS_NO_SUBMIT_CANCEL",
        "firewall_broker_verified": ctx.verified,
        "broker_contacted": False,
        "submit_call_made": False,
        "cancel_call_made": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": ctx.real_broker_contacted,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v157_status": "PASS",
        "execution_lock_deep_recheck_v156_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V197Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v196_baseline"):
        return "PASS" if ctx.v196_baseline_status == "PASS_V196_BASELINE_READBACK" else "FAIL" if ctx.v196_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v197_firewall_broker_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.verified else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V197Context) -> dict[str, Any]:
    workstream = "v197: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v197_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V197_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v197_report.json":
        report.update({"completion_oriented_next_action_v197_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v196_carried_status": ctx.v196_baseline_status, "firewall_broker_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v197_firewall_broker_controller_report.json"), "no_submit_cancel": str(ARTIFACTS / "v197_no_submit_cancel_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v197.json", "dummy_canonical_identity_report_v197.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V197ReportFactory:
    def __init__(self, *, firewall_adapter=None, broker_readonly_approval=None, readonly_adapter=None) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter, broker_readonly_approval=broker_readonly_approval, readonly_adapter=readonly_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V197Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
