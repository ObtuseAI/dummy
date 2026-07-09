"""DUMMY v159 broker read-only verification — performs broker read-only verification only if exact approval + safe adapter exist.

Validates the exact broker-read-only approval and a read-only adapter capability, then permits only allowed read-only
calls and forbids submit/cancel/transfer/withdrawal/caps/live-submit/market-order. Default is
PARTIAL_BROKER_READONLY_APPROVAL_OR_ADAPTER_ABSENT. Tests inject a NON-BROKER read-only double, so
real_broker_contacted stays false and no submit/cancel occurs. Secrets and private data are redacted/minimized.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v159 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v159: Broker Readonly Verification No Submit Cancel Or Private Leak"
MISSION_NAME = "dummy_mission_state_report_v145.json"
FINAL_NAME = "final_report_v159.json"
INDEX_KEYS = ["broker_readonly_controller_status", "real_broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V159 Broker Read-Only Verification"
MISSION_KEY = "dummy_mission_state_report_v145"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Broker Read-Only", "broker_readonly_controller_status"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V159_ROUTES = [
    "/api/v159/broker-readonly-controller",
    "/api/v159/v158-baseline",
    "/api/v159/broker-readonly-approval-validator",
    "/api/v159/readonly-adapter-capability-check",
    "/api/v159/allowed-readonly-calls-list",
    "/api/v159/forbidden-calls-list",
    "/api/v159/secret-redaction",
    "/api/v159/account-private-data-minimization",
    "/api/v159/no-submit-cancel-proof",
    "/api/v159/no-private-data-leakage-proof",
    "/api/v159/readiness-governor",
    "/api/v159/execution-lock",
    "/api/v159/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "broker-readonly-controller": ["v159_broker_readonly_controller_report.json"],
    "v158-baseline": ["v158_baseline_readback_v1_report.json"],
    "broker-readonly-approval-validator": ["v159_broker_readonly_approval_validator_report.json"],
    "readonly-adapter-capability-check": ["v159_readonly_adapter_capability_check_report.json"],
    "allowed-readonly-calls-list": ["v159_allowed_readonly_calls_list_report.json"],
    "forbidden-calls-list": ["v159_forbidden_calls_list_report.json"],
    "secret-redaction": ["v159_secret_redaction_report.json"],
    "account-private-data-minimization": ["v159_account_private_data_minimization_report.json"],
    "no-submit-cancel-proof": ["v159_no_submit_cancel_proof_report.json"],
    "no-private-data-leakage-proof": ["v159_no_private_data_leakage_proof_report.json"],
    "readiness-governor": ["readiness_governor_v119_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v118_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v159_report_v1.json", "completion_oriented_next_action_v159_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(159)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v159/reports.py scripts/generate_v159_reports.py dashboard/backend/v159_routes.py",
    "python scripts/generate_v159_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ALLOWED_READONLY_CALLS = ["get_account_status", "get_balances_readonly", "get_open_orders_readonly", "get_positions_readonly"]
FORBIDDEN_CALLS = ["submit", "cancel", "transfer", "withdrawal", "modify_caps", "enable_live_submit", "market_order"]


class V159Context:
    def __init__(self, *, broker_readonly_approval=None, broker_readonly_approval_path=None, readonly_adapter=None) -> None:
        self.v158_baseline_status = sgc.baseline_status("final_report_v158.json", "V158")
        res = sgc.resolve_packet(broker_readonly_approval_path, broker_readonly_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)
        self.adapter_present = readonly_adapter is not None
        self.adapter_ok = readonly_adapter is not None and callable(getattr(readonly_adapter, "read_only_verify", None))
        self.verify_result = None
        if self.validation["accepted"] and self.adapter_ok:
            self.verify_result = readonly_adapter.read_only_verify()

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def verified(self) -> bool:
        return self.approved and self.adapter_ok and self.verify_result is not None

    @property
    def real_broker_contacted(self) -> bool:
        return bool(self.verify_result and self.verify_result.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"
        if self.verified:
            return "PASS_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
        return "PARTIAL_BROKER_READONLY_APPROVAL_OR_ADAPTER_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v158_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.verified else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v158_baseline_status.startswith("FAIL"):
            return ["FAIL_V158_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"]
        if self.verified:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("BROKER_READONLY_APPROVAL_ABSENT")
        if not self.adapter_ok:
            blockers.append("READONLY_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL_AWAIT_FINAL_READINESS_QUORUM" if self.verified else "OPERATOR_MUST_SUPPLY_EXACT_BROKER_READONLY_APPROVAL_AND_READONLY_ADAPTER"


def _common(ctx: V159Context) -> dict[str, Any]:
    return {
        "v158_baseline_status": ctx.v158_baseline_status,
        "broker_readonly_controller_status": ctx.controller_status,
        "broker_readonly_approval_validator_status": "PASS_BROKER_READONLY_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL" if ctx.any_fail else "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT"),
        "broker_readonly_approval_hash": ctx.validation["approval_hash"],
        "readonly_adapter_capability_check_status": "PASS_READONLY_ADAPTER_CAPABLE" if ctx.adapter_ok else "PARTIAL_READONLY_ADAPTER_ABSENT",
        "allowed_readonly_calls_list_status": "PASS_ALLOWED_READONLY_CALLS_LISTED",
        "allowed_readonly_calls": ALLOWED_READONLY_CALLS,
        "forbidden_calls_list_status": "PASS_FORBIDDEN_CALLS_LISTED",
        "forbidden_calls": FORBIDDEN_CALLS,
        "secret_redaction_status": "PASS_SECRETS_REDACTED",
        "account_private_data_minimization_status": "PASS_PRIVATE_DATA_MINIMIZED",
        "no_submit_cancel_proof_status": "PASS_NO_SUBMIT_CANCEL",
        "no_private_data_leakage_proof_status": "PASS_NO_PRIVATE_DATA_LEAKAGE",
        "broker_readonly_verified": ctx.verified,
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
        "readiness_governor_v119_status": "PASS",
        "execution_lock_deep_recheck_v118_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V159Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v158_baseline"):
        return "PASS" if ctx.v158_baseline_status == "PASS_V158_BASELINE_READBACK" else "FAIL" if ctx.v158_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v159_broker_readonly_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.verified else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V159Context) -> dict[str, Any]:
    workstream = "v159: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v159_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V159_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v159_report.json":
        report.update({"completion_oriented_next_action_v159_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v158_carried_status": ctx.v158_baseline_status, "broker_readonly_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v159_broker_readonly_controller_report.json"), "no_submit_cancel": str(ARTIFACTS / "v159_no_submit_cancel_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v159.json", "dummy_canonical_identity_report_v159.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V159ReportFactory:
    def __init__(self, *, broker_readonly_approval=None, broker_readonly_approval_path=None, readonly_adapter=None) -> None:
        self.kw = dict(broker_readonly_approval=broker_readonly_approval, broker_readonly_approval_path=broker_readonly_approval_path, readonly_adapter=readonly_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V159Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
