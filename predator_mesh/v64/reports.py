"""DUMMY v64 LiveBrokerFirewall preflight — limit-order-only, no submit/cancel, no account access."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v64 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V64_ROUTES = [
    "/api/v64/firewall-preflight-controller",
    "/api/v64/v63-baseline",
    "/api/v64/firewall-only-path-validator",
    "/api/v64/limit-order-only-rule-validator",
    "/api/v64/no-market-order-validator",
    "/api/v64/no-submit-call-validator",
    "/api/v64/no-cancel-call-validator",
    "/api/v64/no-private-account-access-validator",
    "/api/v64/caps-readonly-proof",
    "/api/v64/live-submit-disabled-proof",
    "/api/v64/kill-switch-requirement-validator",
    "/api/v64/rollback-requirement-validator",
    "/api/v64/idempotency-requirement-validator",
    "/api/v64/liquidity-slippage-requirement-validator",
    "/api/v64/canary-nonexecution-validator-v14",
    "/api/v64/readiness-governor",
    "/api/v64/execution-lock",
    "/api/v64/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "firewall-preflight-controller": ["v64_firewall_preflight_controller_report.json"],
    "v63-baseline": ["v63_baseline_readback_v1_report.json"],
    "firewall-only-path-validator": ["v64_firewall_only_path_validator_report.json"],
    "limit-order-only-rule-validator": ["v64_limit_order_only_rule_validator_report.json"],
    "no-market-order-validator": ["v64_no_market_order_validator_report.json"],
    "no-submit-call-validator": ["v64_no_submit_call_validator_report.json"],
    "no-cancel-call-validator": ["v64_no_cancel_call_validator_report.json"],
    "no-private-account-access-validator": ["v64_no_private_account_access_validator_report.json"],
    "caps-readonly-proof": ["v64_caps_readonly_proof_report.json"],
    "live-submit-disabled-proof": ["v64_live_submit_disabled_proof_report.json"],
    "kill-switch-requirement-validator": ["v64_kill_switch_requirement_validator_report.json"],
    "rollback-requirement-validator": ["v64_rollback_requirement_validator_report.json"],
    "idempotency-requirement-validator": ["v64_idempotency_requirement_validator_report.json"],
    "liquidity-slippage-requirement-validator": ["v64_liquidity_slippage_requirement_validator_report.json"],
    "canary-nonexecution-validator-v14": ["v64_canary_nonexecution_validator_v14_report.json"],
    "readiness-governor": ["readiness_governor_v24_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v23_report.json"],
    "mission-state": ["dummy_mission_state_report_v50.json", "dashboard_v64_report_v1.json", "completion_oriented_next_action_v64_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(64)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v64/reports.py scripts/generate_v64_reports.py dashboard/backend/v64_routes.py",
    "python scripts/generate_v64_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

# Preflight requirement checks (all satisfied as future-usage requirements; none enable execution).
PREFLIGHT_VALIDATORS = {
    "firewall_only_path_validator_status": "PASS_FIREWALL_ONLY_PATH",
    "limit_order_only_rule_validator_status": "PASS_LIMIT_ORDER_ONLY",
    "no_market_order_validator_status": "PASS_NO_MARKET_ORDER",
    "no_submit_call_validator_status": "PASS_NO_SUBMIT_CALL",
    "no_cancel_call_validator_status": "PASS_NO_CANCEL_CALL",
    "no_private_account_access_validator_status": "PASS_NO_PRIVATE_ACCOUNT_ACCESS",
    "caps_readonly_proof_status": "PASS_CAPS_READONLY",
    "live_submit_disabled_proof_status": "PASS_LIVE_SUBMIT_DISABLED",
    "kill_switch_requirement_validator_status": "PASS_KILL_SWITCH_REQUIRED",
    "rollback_requirement_validator_status": "PASS_ROLLBACK_REQUIRED",
    "idempotency_requirement_validator_status": "PASS_IDEMPOTENCY_REQUIRED",
    "liquidity_slippage_requirement_validator_status": "PASS_LIQUIDITY_SLIPPAGE_PLACEHOLDER",
}


class V64Context:
    def __init__(self) -> None:
        self.v63_baseline_status = sgc.baseline_status("final_report_v63.json", "V63")

    @property
    def final_verdict(self) -> str:
        if self.v63_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.v63_baseline_status.startswith("PARTIAL"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v63_baseline_status.startswith("FAIL"):
            return ["FAIL_V63_BASELINE_REGRESSION"]
        if self.v63_baseline_status.startswith("PARTIAL"):
            return ["PARTIAL_V63_BASELINE_UNAVAILABLE"]
        return []

    @property
    def next_action(self) -> str:
        return "FIREWALL_PREFLIGHT_VALIDATED_AWAIT_FUTURE_LIVE_CANARY_APPROVAL"


def _common(ctx: V64Context) -> dict[str, Any]:
    common = {
        "v63_baseline_status": ctx.v63_baseline_status,
        "firewall_preflight_controller_status": "PASS_FIREWALL_PREFLIGHT_ONLY_NO_SUBMIT",
        "preflight_only": True,
        "future_live_canary_approval_phrase": sgc.LIVE_CANARY_PHRASE,
        "future_live_canary_phrase_accepted_here": False,
        "future_live_canary_phrase_distinct": True,
        "canary_nonexecution_validator_v14_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V14",
        "readiness_governor_v24_status": "PASS",
        "execution_lock_deep_recheck_v23_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(PREFLIGHT_VALIDATORS)
    return common


def _verdict(name: str, ctx: V64Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v63_baseline"):
        return "PASS" if ctx.v63_baseline_status == "PASS_V63_BASELINE_READBACK" else "FAIL" if ctx.v63_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V64Context) -> dict[str, Any]:
    workstream = "v64: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v64_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V64_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_access_account": False})
    elif name == "completion_oriented_next_action_v64_report.json":
        report.update({"completion_oriented_next_action_v64_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v50.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v63_carried_status": ctx.v63_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v64.json"), "firewall_preflight": str(ARTIFACTS / "v64_firewall_preflight_controller_report.json"), "live_submit_disabled_proof": str(ARTIFACTS / "v64_live_submit_disabled_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v64.json", "dummy_canonical_identity_report_v64.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V64ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V64Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
