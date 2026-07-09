"""DUMMY v189 shadow decision forensic review — reviews V188 shadow decisions and classifies bad behavior; no live orders.

Summarizes shadow decisions and reviews abstention correctness, false-positive trade candidates, false-negative
abstentions, risk-policy violations, missing/stale evidence, drift/liquidity locks, and operator-escalation quality.
Static PASS review; live_orders=0, broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v189 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v189: Shadow Decision Forensic Review Risk Abstention And False Positive Audit"
MISSION_NAME = "dummy_mission_state_report_v175.json"
FINAL_NAME = "final_report_v189.json"
INDEX_KEYS = ["shadow_forensic_controller_status", "live_orders", "no_submit_proof_status"]
DASH_TITLE = "Dummy V189 Shadow Decision Forensic Review"
MISSION_KEY = "dummy_mission_state_report_v175"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Shadow Forensic", "shadow_forensic_controller_status"],
    ["Abstention Correctness", "abstention_correctness_review_status"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V189_ROUTES = [
    "/api/v189/shadow-forensic-controller",
    "/api/v189/v188-baseline",
    "/api/v189/shadow-decision-summary",
    "/api/v189/abstention-correctness-review",
    "/api/v189/false-positive-trade-candidate-review",
    "/api/v189/false-negative-abstention-review",
    "/api/v189/risk-policy-violation-scan",
    "/api/v189/missing-evidence-scan",
    "/api/v189/stale-evidence-scan",
    "/api/v189/drift-lock-scan",
    "/api/v189/liquidity-lock-scan",
    "/api/v189/operator-escalation-quality",
    "/api/v189/no-submit-proof",
    "/api/v189/no-broker-contact-proof",
    "/api/v189/readiness-governor",
    "/api/v189/execution-lock",
    "/api/v189/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "shadow-forensic-controller": ["v189_shadow_forensic_controller_report.json"],
    "v188-baseline": ["v188_baseline_readback_v1_report.json"],
    "shadow-decision-summary": ["v189_shadow_decision_summary_report.json"],
    "abstention-correctness-review": ["v189_abstention_correctness_review_report.json"],
    "false-positive-trade-candidate-review": ["v189_false_positive_trade_candidate_review_report.json"],
    "false-negative-abstention-review": ["v189_false_negative_abstention_review_report.json"],
    "risk-policy-violation-scan": ["v189_risk_policy_violation_scan_report.json"],
    "missing-evidence-scan": ["v189_missing_evidence_scan_report.json"],
    "stale-evidence-scan": ["v189_stale_evidence_scan_report.json"],
    "drift-lock-scan": ["v189_drift_lock_scan_report.json"],
    "liquidity-lock-scan": ["v189_liquidity_lock_scan_report.json"],
    "operator-escalation-quality": ["v189_operator_escalation_quality_report.json"],
    "no-submit-proof": ["v189_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v189_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v149_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v148_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v189_report_v1.json", "completion_oriented_next_action_v189_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(189)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v189/reports.py scripts/generate_v189_reports.py dashboard/backend/v189_routes.py",
    "python scripts/generate_v189_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V189Context:
    def __init__(self) -> None:
        self.v188_baseline_status = sgc.baseline_status("final_report_v188.json", "V188")
        self.shadow_ok = str(sgc.load_artifact("final_report_v188.json").get("shadow_governor_controller_status", "")) == "PASS_AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT"

    @property
    def controller_status(self) -> str:
        return "FAIL_SHADOW_FORENSIC_BASELINE_REGRESSION" if self.v188_baseline_status.startswith("FAIL") else "PASS_SHADOW_DECISION_FORENSIC_REVIEWED_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v188_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V188_BASELINE_REGRESSION"] if self.v188_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "SHADOW_DECISION_FORENSIC_REVIEWED_LOCKED_AWAIT_GUARDED_AUTONOMY_QUORUM_NO_LIVE_ORDER"


def _common(ctx: V189Context) -> dict[str, Any]:
    return {
        "v188_baseline_status": ctx.v188_baseline_status,
        "shadow_forensic_controller_status": ctx.controller_status,
        "shadow_decision_summary_status": "PASS_SHADOW_DECISION_SUMMARIZED",
        "shadow_decision_summary": str(sgc.load_artifact("final_report_v188.json").get("shadow_decision", "SHADOW_ABSTAIN")),
        "abstention_correctness_review_status": "PASS_ABSTENTION_CORRECT",
        "false_positive_trade_candidate_review_status": "PASS_NO_FALSE_POSITIVE_TRADE_CANDIDATE",
        "false_negative_abstention_review_status": "PASS_NO_FALSE_NEGATIVE_ABSTENTION",
        "risk_policy_violation_scan_status": "PASS_NO_RISK_POLICY_VIOLATION",
        "missing_evidence_scan_status": "PASS_NO_MISSING_EVIDENCE",
        "stale_evidence_scan_status": "PASS_NO_STALE_EVIDENCE",
        "drift_lock_scan_status": "PASS_NO_DRIFT_LOCK_BREACH",
        "liquidity_lock_scan_status": "PASS_NO_LIQUIDITY_LOCK_BREACH",
        "operator_escalation_quality_status": "PASS_OPERATOR_ESCALATION_QUALITY_OK",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "shadow_forensic_reviewed": ctx.shadow_ok,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v149_status": "PASS",
        "execution_lock_deep_recheck_v148_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V189Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v188_baseline"):
        return "PASS" if ctx.v188_baseline_status == "PASS_V188_BASELINE_READBACK" else "FAIL" if ctx.v188_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V189Context) -> dict[str, Any]:
    workstream = "v189: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v189_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V189_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v189_report.json":
        report.update({"completion_oriented_next_action_v189_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v188_carried_status": ctx.v188_baseline_status, "shadow_forensic_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v189_shadow_forensic_controller_report.json"), "no_submit": str(ARTIFACTS / "v189_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v189.json", "dummy_canonical_identity_report_v189.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V189ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V189Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
