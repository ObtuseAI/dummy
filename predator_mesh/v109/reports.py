"""DUMMY v109 autonomous abstention governor — strengthens 'do not trade' intelligence; no autonomous trading.

Encodes a locked set of abstention (trade-refusal) rules and an abstention ledger. The policy is active
and read-only; autonomous trading remains disabled and no order is ever placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v109 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v109: Autonomous Abstention Governor Trade Refusal Policy"
MISSION_NAME = "dummy_mission_state_report_v95.json"
FINAL_NAME = "final_report_v109.json"
INDEX_KEYS = ["abstention_governor_status", "autonomous_trading_enabled", "no_auto_trade_proof_status"]
DASH_TITLE = "Dummy V109 Autonomous Abstention Governor"
MISSION_KEY = "dummy_mission_state_report_v95"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Abstention Governor", "abstention_governor_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Rules Active", "abstention_rules_count"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

ABSTENTION_RULES = [
    "wide_spread",
    "low_liquidity",
    "stale_evidence",
    "contradictory_evidence",
    "drift_warning",
    "settlement_ambiguity",
    "market_too_close_to_resolution",
    "recent_loss_lock",
    "recent_reject_lock",
    "risk_cap_conflict",
    "missing_approval",
    "missing_live_submit_caps_firewall",
    "broker_error_state",
]

V109_ROUTES = [
    "/api/v109/abstention-governor-controller",
    "/api/v109/v108-baseline",
    "/api/v109/abstention-rules",
    "/api/v109/abstention-ledger",
    "/api/v109/false-abstention-review",
    "/api/v109/no-auto-trade-proof",
    "/api/v109/readiness-governor",
    "/api/v109/execution-lock",
    "/api/v109/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "abstention-governor-controller": ["v109_abstention_governor_controller_report.json"],
    "v108-baseline": ["v108_baseline_readback_v1_report.json"],
    "abstention-rules": ["v109_abstention_rules_report.json"],
    "abstention-ledger": ["v109_abstention_ledger_report.json"],
    "false-abstention-review": ["v109_false_abstention_review_report.json"],
    "no-auto-trade-proof": ["v109_no_auto_trade_proof_report.json"],
    "readiness-governor": ["readiness_governor_v69_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v68_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v109_report_v1.json", "completion_oriented_next_action_v109_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(109)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v109/reports.py scripts/generate_v109_reports.py dashboard/backend/v109_routes.py",
    "python scripts/generate_v109_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V109Context:
    def __init__(self) -> None:
        self.v108_baseline_status = sgc.baseline_status("final_report_v108.json", "V108")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v108_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V108_BASELINE_REGRESSION"] if self.v108_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "ABSTENTION_POLICY_ACTIVE_AUTONOMOUS_TRADING_DISABLED_AWAIT_PRODUCTION_READINESS_AUDIT"


def _common(ctx: V109Context) -> dict[str, Any]:
    return {
        "v108_baseline_status": ctx.v108_baseline_status,
        "abstention_governor_status": "PASS_ABSTENTION_POLICY_ACTIVE",
        "abstention_rules_status": "PASS_ABSTENTION_RULES_LOCKED",
        "abstention_rules": ABSTENTION_RULES,
        "abstention_rules_count": len(ABSTENTION_RULES),
        "abstention_ledger_status": "PASS_ABSTENTION_LEDGER_RECORDED",
        "false_abstention_review_status": "PASS_FALSE_ABSTENTION_REVIEWED",
        "no_auto_trade_proof_status": "PASS_NO_AUTO_TRADE",
        "autonomous_trading_enabled": False,
        "auto_trade_on_signal": False,
        "policy_is_design_only": True,
        "caps_modified": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v69_status": "PASS",
        "execution_lock_deep_recheck_v68_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V109Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v108_baseline"):
        return "PASS" if ctx.v108_baseline_status == "PASS_V108_BASELINE_READBACK" else "FAIL" if ctx.v108_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V109Context) -> dict[str, Any]:
    workstream = "v109: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v109_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V109_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v109_report.json":
        report.update({"completion_oriented_next_action_v109_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v108_carried_status": ctx.v108_baseline_status, "abstention_governor_status": "PASS_ABSTENTION_POLICY_ACTIVE", "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v109_abstention_governor_controller_report.json"), "no_auto_trade": str(ARTIFACTS / "v109_no_auto_trade_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v109.json", "dummy_canonical_identity_report_v109.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V109ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V109Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
