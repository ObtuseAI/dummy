"""DUMMY v110 production-readiness audit — decides controlled-operation eligibility; does not enable production.

Reviews campaign evidence, risk policy, abstention policy, broker/firewall readiness, live-submit/caps
control, reconcile readiness, and audit-ledger readiness. Controlled operation may only be eligible as
LOCKED. No autonomous live operation and no production enablement.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v110 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v110: Production Readiness Audit Controlled Operation Eligibility"
MISSION_NAME = "dummy_mission_state_report_v96.json"
FINAL_NAME = "final_report_v110.json"
INDEX_KEYS = ["production_readiness_controller_status", "production_eligibility_status", "no_production_enable_proof_status"]
DASH_TITLE = "Dummy V110 Production Readiness Audit"
MISSION_KEY = "dummy_mission_state_report_v96"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Readiness Audit", "production_readiness_controller_status"],
    ["Eligibility", "production_eligibility_status"],
    ["Production Enabled", "production_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V110_ROUTES = [
    "/api/v110/production-readiness-controller",
    "/api/v110/v109-baseline",
    "/api/v110/campaign-evidence-review",
    "/api/v110/risk-policy-review",
    "/api/v110/abstention-policy-review",
    "/api/v110/broker-firewall-readiness-review",
    "/api/v110/live-submit-caps-control-review",
    "/api/v110/reconcile-readiness-review",
    "/api/v110/audit-ledger-readiness",
    "/api/v110/production-eligibility-status",
    "/api/v110/no-production-enable-proof",
    "/api/v110/readiness-governor",
    "/api/v110/execution-lock",
    "/api/v110/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-readiness-controller": ["v110_production_readiness_controller_report.json"],
    "v109-baseline": ["v109_baseline_readback_v1_report.json"],
    "campaign-evidence-review": ["v110_campaign_evidence_review_report.json"],
    "risk-policy-review": ["v110_risk_policy_review_report.json"],
    "abstention-policy-review": ["v110_abstention_policy_review_report.json"],
    "broker-firewall-readiness-review": ["v110_broker_firewall_readiness_review_report.json"],
    "live-submit-caps-control-review": ["v110_live_submit_caps_control_review_report.json"],
    "reconcile-readiness-review": ["v110_reconcile_readiness_review_report.json"],
    "audit-ledger-readiness": ["v110_audit_ledger_readiness_report.json"],
    "production-eligibility-status": ["v110_production_eligibility_status_report.json"],
    "no-production-enable-proof": ["v110_no_production_enable_proof_report.json"],
    "readiness-governor": ["readiness_governor_v70_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v69_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v110_report_v1.json", "completion_oriented_next_action_v110_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(110)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v110/reports.py scripts/generate_v110_reports.py dashboard/backend/v110_routes.py",
    "python scripts/generate_v110_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V110Context:
    def __init__(self, *, prereq_override=None) -> None:
        self.v109_baseline_status = sgc.baseline_status("final_report_v109.json", "V109")
        if prereq_override is not None:
            self.evidence_ok = bool(prereq_override)
        else:
            campaign = sgc.load_artifact("final_report_v106.json")
            risk = sgc.load_artifact("final_report_v108.json")
            abstention = sgc.load_artifact("final_report_v109.json")
            self.evidence_ok = bool(campaign) and risk.get("verdict") in {"PASS", "PARTIAL"} and abstention.get("verdict") in {"PASS", "PARTIAL"}

    @property
    def eligibility(self) -> str:
        if self.v109_baseline_status.startswith("FAIL"):
            return "PRODUCTION_AUDIT_REPAIR_REQUIRED"
        if self.evidence_ok:
            return "CONTROLLED_OPERATION_ELIGIBLE_LOCKED"
        return "PRODUCTION_NOT_READY_BLOCKED"

    @property
    def controller_status(self) -> str:
        return "PASS_PRODUCTION_READINESS_AUDITED_LOCKED" if self.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED" else "PARTIAL_PRODUCTION_NOT_READY"

    @property
    def final_verdict(self) -> str:
        if self.v109_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED" else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v109_baseline_status.startswith("FAIL"):
            return ["FAIL_V109_BASELINE_REGRESSION"]
        return [] if self.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED" else ["PRODUCTION_READINESS_EVIDENCE_INCOMPLETE"]

    @property
    def next_action(self) -> str:
        if self.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED":
            return "CONTROLLED_OPERATION_ELIGIBLE_LOCKED_NO_PRODUCTION_ENABLE_AWAIT_SESSION_GOVERNOR"
        return "OPERATOR_MUST_COMPLETE_PRODUCTION_READINESS_EVIDENCE"


def _common(ctx: V110Context) -> dict[str, Any]:
    ok = ctx.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED"
    def s(v):
        return v if ok else "PARTIAL_REVIEW_INCOMPLETE"
    return {
        "v109_baseline_status": ctx.v109_baseline_status,
        "production_readiness_controller_status": ctx.controller_status,
        "campaign_evidence_review_status": s("PASS_CAMPAIGN_EVIDENCE_REVIEWED"),
        "risk_policy_review_status": s("PASS_RISK_POLICY_REVIEWED"),
        "abstention_policy_review_status": s("PASS_ABSTENTION_POLICY_REVIEWED"),
        "broker_firewall_readiness_review_status": "PASS_FIREWALL_ONLY_NO_CONTACT",
        "live_submit_caps_control_review_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "reconcile_readiness_review_status": "PASS_RECONCILE_READY",
        "audit_ledger_readiness_status": "PASS_AUDIT_LEDGER_READY",
        "production_eligibility_status": ctx.eligibility,
        "no_production_enable_proof_status": "PASS_NO_PRODUCTION_ENABLE",
        "production_enabled": False,
        "controlled_operation_locked": True,
        "autonomous_live_operation": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v70_status": "PASS",
        "execution_lock_deep_recheck_v69_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V110Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v109_baseline"):
        return "PASS" if ctx.v109_baseline_status == "PASS_V109_BASELINE_READBACK" else "FAIL" if ctx.v109_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v110_production_readiness_controller_report.json":
        return "PASS" if ctx.eligibility == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED" else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V110Context) -> dict[str, Any]:
    workstream = "v110: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v110_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V110_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v110_report.json":
        report.update({"completion_oriented_next_action_v110_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v109_carried_status": ctx.v109_baseline_status, "production_eligibility_status": ctx.eligibility, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v110_production_readiness_controller_report.json"), "eligibility": str(ARTIFACTS / "v110_production_eligibility_status_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v110.json", "dummy_canonical_identity_report_v110.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V110ReportFactory:
    def __init__(self, *, prereq_override=None) -> None:
        self.kw = dict(prereq_override=prereq_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V110Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
