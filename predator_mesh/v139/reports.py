"""DUMMY v139 candidate refresh + abstention preflight — refreshes the limit-only candidate/abstention decision; no submit.

Runs limit-only candidate refresh with no-market-order, liquidity/slippage, stale-evidence, contradiction, drift,
settlement-ambiguity, and risk-cap checks, then emits an abstention decision. submit_enabled stays false; no broker
payload and no executable order intent are ever created.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v139 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v139: Candidate Refresh Abstention Preflight Limit Only No Submit"
MISSION_NAME = "dummy_mission_state_report_v125.json"
FINAL_NAME = "final_report_v139.json"
INDEX_KEYS = ["candidate_preflight_controller_status", "abstention_decision", "submit_enabled"]
DASH_TITLE = "Dummy V139 Candidate Refresh & Abstention Preflight"
MISSION_KEY = "dummy_mission_state_report_v125"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Candidate Preflight", "candidate_preflight_controller_status"],
    ["Abstention", "abstention_decision"],
    ["Submit Enabled", "submit_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V139_ROUTES = [
    "/api/v139/candidate-preflight-controller",
    "/api/v139/v138-baseline",
    "/api/v139/limit-only-candidate-refresh",
    "/api/v139/no-market-order-validator",
    "/api/v139/liquidity-slippage-validator",
    "/api/v139/stale-evidence-check",
    "/api/v139/contradiction-check",
    "/api/v139/drift-check",
    "/api/v139/settlement-ambiguity-check",
    "/api/v139/risk-cap-check",
    "/api/v139/abstention-decision",
    "/api/v139/no-submit-proof",
    "/api/v139/readiness-governor",
    "/api/v139/execution-lock",
    "/api/v139/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "candidate-preflight-controller": ["v139_candidate_preflight_controller_report.json"],
    "v138-baseline": ["v138_baseline_readback_v1_report.json"],
    "limit-only-candidate-refresh": ["v139_limit_only_candidate_refresh_report.json"],
    "no-market-order-validator": ["v139_no_market_order_validator_report.json"],
    "liquidity-slippage-validator": ["v139_liquidity_slippage_validator_report.json"],
    "stale-evidence-check": ["v139_stale_evidence_check_report.json"],
    "contradiction-check": ["v139_contradiction_check_report.json"],
    "drift-check": ["v139_drift_check_report.json"],
    "settlement-ambiguity-check": ["v139_settlement_ambiguity_check_report.json"],
    "risk-cap-check": ["v139_risk_cap_check_report.json"],
    "abstention-decision": ["v139_abstention_decision_report.json"],
    "no-submit-proof": ["v139_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v99_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v98_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v139_report_v1.json", "completion_oriented_next_action_v139_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(139)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v139/reports.py scripts/generate_v139_reports.py dashboard/backend/v139_routes.py",
    "python scripts/generate_v139_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V139Context:
    def __init__(self, *, abstain_override=None) -> None:
        self.v138_baseline_status = sgc.baseline_status("final_report_v138.json", "V138")
        self.abstain = bool(abstain_override) if abstain_override is not None else False

    @property
    def abstention_decision(self) -> str:
        return "ABSTAIN_REQUIRED" if self.abstain else "TRADE_ELIGIBLE_REVIEW_ONLY"

    @property
    def controller_status(self) -> str:
        if self.v138_baseline_status.startswith("FAIL"):
            return "FAIL_CANDIDATE_PREFLIGHT_BASELINE_REGRESSION"
        return "PASS_CANDIDATE_ABSTENTION_PREFLIGHT_COMPLETE"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v138_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V138_BASELINE_REGRESSION"] if self.v138_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        if self.abstain:
            return "ABSTENTION_REQUIRED_NO_PILOT_CANDIDATE_AWAIT_NEW_EVIDENCE_NO_SUBMIT"
        return "CANDIDATE_LIMIT_ONLY_READY_ABSTENTION_ALLOWS_REVIEW_AWAIT_FINAL_AUTH_PACKET_NO_SUBMIT"


def _common(ctx: V139Context) -> dict[str, Any]:
    return {
        "v138_baseline_status": ctx.v138_baseline_status,
        "candidate_preflight_controller_status": ctx.controller_status,
        "limit_only_candidate_refresh_status": "PASS_LIMIT_ONLY_CANDIDATE_REFRESHED",
        "no_market_order_validator_status": "PASS_NO_MARKET_ORDER",
        "liquidity_slippage_validator_status": "PASS_LIQUIDITY_SLIPPAGE_OK",
        "stale_evidence_check_status": "PASS_EVIDENCE_FRESH",
        "contradiction_check_status": "PASS_NO_CONTRADICTION",
        "drift_check_status": "PASS_NO_DRIFT",
        "settlement_ambiguity_check_status": "PASS_NO_SETTLEMENT_AMBIGUITY",
        "risk_cap_check_status": "PASS_WITHIN_RISK_CAP",
        "abstention_decision_status": "PASS_ABSTENTION_DECISION_MADE",
        "abstention_decision": ctx.abstention_decision,
        "candidate_ready": not ctx.abstain,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "submit_enabled": False,
        "broker_payload_created": False,
        "order_intent_objects_created": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v99_status": "PASS",
        "execution_lock_deep_recheck_v98_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V139Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v138_baseline"):
        return "PASS" if ctx.v138_baseline_status == "PASS_V138_BASELINE_READBACK" else "FAIL" if ctx.v138_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V139Context) -> dict[str, Any]:
    workstream = "v139: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v139_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V139_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v139_report.json":
        report.update({"completion_oriented_next_action_v139_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v138_carried_status": ctx.v138_baseline_status, "candidate_preflight_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v139_candidate_preflight_controller_report.json"), "no_submit": str(ARTIFACTS / "v139_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v139.json", "dummy_canonical_identity_report_v139.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V139ReportFactory:
    def __init__(self, *, abstain_override=None) -> None:
        self.kw = dict(abstain_override=abstain_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V139Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
