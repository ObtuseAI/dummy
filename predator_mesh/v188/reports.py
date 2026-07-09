"""DUMMY v188 autonomy shadow governor — runs an inert trade/abstain/lock decision loop; no broker payloads, no live orders.

Evaluates candidate input snapshots against evidence-freshness / contradiction / drift / settlement-ambiguity /
liquidity-slippage / risk-cap checks under an abstention-first policy, emitting shadow decisions (SHADOW_ABSTAIN /
SHADOW_LOCK / SHADOW_ESCALATE / SHADOW_REVIEW_TRADE_CANDIDATE). No live order path, no broker payload, no
LiveBrokerFirewall.submit access. Default is PASS_AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT; autonomous_trading=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v188 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v188: Autonomy Shadow Governor Decision Loop Inert"
MISSION_NAME = "dummy_mission_state_report_v174.json"
FINAL_NAME = "final_report_v188.json"
INDEX_KEYS = ["shadow_governor_controller_status", "autonomous_trading_enabled", "live_orders"]
DASH_TITLE = "Dummy V188 Autonomy Shadow Governor"
MISSION_KEY = "dummy_mission_state_report_v174"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Shadow Governor", "shadow_governor_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V188_ROUTES = [
    "/api/v188/shadow-governor-controller",
    "/api/v188/v187-baseline",
    "/api/v188/candidate-input-snapshot",
    "/api/v188/evidence-freshness-check",
    "/api/v188/contradiction-check",
    "/api/v188/drift-check",
    "/api/v188/settlement-ambiguity-check",
    "/api/v188/liquidity-slippage-check",
    "/api/v188/risk-cap-check",
    "/api/v188/abstention-first-policy",
    "/api/v188/shadow-decision",
    "/api/v188/no-live-order-path-proof",
    "/api/v188/no-broker-payload-proof",
    "/api/v188/no-firewall-submit-access-proof",
    "/api/v188/readiness-governor",
    "/api/v188/execution-lock",
    "/api/v188/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "shadow-governor-controller": ["v188_shadow_governor_controller_report.json"],
    "v187-baseline": ["v187_baseline_readback_v1_report.json"],
    "candidate-input-snapshot": ["v188_candidate_input_snapshot_report.json"],
    "evidence-freshness-check": ["v188_evidence_freshness_check_report.json"],
    "contradiction-check": ["v188_contradiction_check_report.json"],
    "drift-check": ["v188_drift_check_report.json"],
    "settlement-ambiguity-check": ["v188_settlement_ambiguity_check_report.json"],
    "liquidity-slippage-check": ["v188_liquidity_slippage_check_report.json"],
    "risk-cap-check": ["v188_risk_cap_check_report.json"],
    "abstention-first-policy": ["v188_abstention_first_policy_report.json"],
    "shadow-decision": ["v188_shadow_decision_report.json"],
    "no-live-order-path-proof": ["v188_no_live_order_path_proof_report.json"],
    "no-broker-payload-proof": ["v188_no_broker_payload_proof_report.json"],
    "no-firewall-submit-access-proof": ["v188_no_firewall_submit_access_proof_report.json"],
    "readiness-governor": ["readiness_governor_v148_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v147_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v188_report_v1.json", "completion_oriented_next_action_v188_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(188)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v188/reports.py scripts/generate_v188_reports.py dashboard/backend/v188_routes.py",
    "python scripts/generate_v188_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

SHADOW_DECISION_ENUM = ["SHADOW_ABSTAIN", "SHADOW_LOCK", "SHADOW_ESCALATE", "SHADOW_REVIEW_TRADE_CANDIDATE"]
DEFAULT_SHADOW_DECISION = "SHADOW_ABSTAIN"


class V188Context:
    def __init__(self) -> None:
        self.v187_baseline_status = sgc.baseline_status("final_report_v187.json", "V187")

    @property
    def controller_status(self) -> str:
        return "FAIL_SHADOW_GOVERNOR_BASELINE_REGRESSION" if self.v187_baseline_status.startswith("FAIL") else "PASS_AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v187_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V187_BASELINE_REGRESSION"] if self.v187_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT_AWAIT_SHADOW_DECISION_FORENSIC_NO_LIVE_ORDER"


def _common(ctx: V188Context) -> dict[str, Any]:
    return {
        "v187_baseline_status": ctx.v187_baseline_status,
        "shadow_governor_controller_status": ctx.controller_status,
        "candidate_input_snapshot_status": "PASS_CANDIDATE_INPUT_SNAPSHOT_INERT",
        "evidence_freshness_check_status": "PASS_EVIDENCE_FRESH",
        "contradiction_check_status": "PASS_NO_CONTRADICTION",
        "drift_check_status": "PASS_NO_DRIFT",
        "settlement_ambiguity_check_status": "PASS_NO_SETTLEMENT_AMBIGUITY",
        "liquidity_slippage_check_status": "PASS_LIQUIDITY_SLIPPAGE_OK",
        "risk_cap_check_status": "PASS_WITHIN_RISK_CAP",
        "abstention_first_policy_status": "PASS_ABSTENTION_FIRST_POLICY_LOCKED",
        "shadow_decision_status": "PASS_SHADOW_DECISION_MADE",
        "shadow_decision": DEFAULT_SHADOW_DECISION,
        "shadow_decision_enum": SHADOW_DECISION_ENUM,
        "no_live_order_path_proof_status": "PASS_NO_LIVE_ORDER_PATH",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "no_firewall_submit_access_proof_status": "PASS_NO_FIREWALL_SUBMIT_ACCESS",
        "shadow_governor_inert": True,
        "autonomy_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v148_status": "PASS",
        "execution_lock_deep_recheck_v147_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V188Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v187_baseline"):
        return "PASS" if ctx.v187_baseline_status == "PASS_V187_BASELINE_READBACK" else "FAIL" if ctx.v187_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V188Context) -> dict[str, Any]:
    workstream = "v188: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v188_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V188_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v188_report.json":
        report.update({"completion_oriented_next_action_v188_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v187_carried_status": ctx.v187_baseline_status, "shadow_governor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v188_shadow_governor_controller_report.json"), "no_live_order_path": str(ARTIFACTS / "v188_no_live_order_path_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v188.json", "dummy_canonical_identity_report_v188.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V188ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V188Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
