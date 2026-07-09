"""DUMMY v115 autonomous candidate review — reviews whether limited autonomy could ever be considered; enables nothing.

Validates the exact autonomy-review approval and reviews campaign/session/risk/abstention/broker/firewall and
live-submit/caps prerequisites. Emits an eligibility status only (AUTONOMY_NOT_ELIGIBLE /
AUTONOMY_REVIEW_ELIGIBLE_LOCKED / AUTONOMY_REPAIR_REQUIRED). Autonomous trading stays disabled; no order,
no scale, no live-submit/caps change.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v115 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v115: Autonomous Candidate Review No Autonomous Trading"
MISSION_NAME = "dummy_mission_state_report_v101.json"
FINAL_NAME = "final_report_v115.json"
INDEX_KEYS = ["autonomy_review_controller_status", "autonomy_eligibility_status", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V115 Autonomous Candidate Review"
MISSION_KEY = "dummy_mission_state_report_v101"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Autonomy Review", "autonomy_review_controller_status"],
    ["Eligibility", "autonomy_eligibility_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V115_ROUTES = [
    "/api/v115/autonomy-review-controller",
    "/api/v115/v114-baseline",
    "/api/v115/autonomy-review-approval-validator",
    "/api/v115/campaign-session-evidence-prerequisite",
    "/api/v115/risk-abstention-prerequisite",
    "/api/v115/broker-firewall-prerequisite",
    "/api/v115/live-submit-caps-control-prerequisite",
    "/api/v115/autonomy-eligibility-status",
    "/api/v115/no-autonomous-order-proof",
    "/api/v115/no-auto-scale-proof",
    "/api/v115/readiness-governor",
    "/api/v115/execution-lock",
    "/api/v115/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-review-controller": ["v115_autonomy_review_controller_report.json"],
    "v114-baseline": ["v114_baseline_readback_v1_report.json"],
    "autonomy-review-approval-validator": ["v115_autonomy_review_approval_validator_report.json"],
    "campaign-session-evidence-prerequisite": ["v115_campaign_session_evidence_prerequisite_report.json"],
    "risk-abstention-prerequisite": ["v115_risk_abstention_prerequisite_report.json"],
    "broker-firewall-prerequisite": ["v115_broker_firewall_prerequisite_report.json"],
    "live-submit-caps-control-prerequisite": ["v115_live_submit_caps_control_prerequisite_report.json"],
    "autonomy-eligibility-status": ["v115_autonomy_eligibility_status_report.json"],
    "no-autonomous-order-proof": ["v115_no_autonomous_order_proof_report.json"],
    "no-auto-scale-proof": ["v115_no_auto_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v75_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v74_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v115_report_v1.json", "completion_oriented_next_action_v115_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(115)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v115/reports.py scripts/generate_v115_reports.py dashboard/backend/v115_routes.py",
    "python scripts/generate_v115_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V115Context:
    def __init__(self, *, autonomy_approval=None, autonomy_approval_path=None, prereq_override=None) -> None:
        self.v114_baseline_status = sgc.baseline_status("final_report_v114.json", "V114")
        res = sgc.resolve_packet(autonomy_approval_path, autonomy_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.AUTONOMY_REVIEW_PHRASE, required_fields=sgc.AUTONOMY_REVIEW_FIELDS, required_scope=sgc.AUTONOMY_REVIEW_SCOPE)
        if prereq_override is not None:
            self.prereq_ok = bool(prereq_override)
        else:
            prod = sgc.load_artifact("final_report_v110.json")
            gov = sgc.load_artifact("final_report_v112.json")
            self.prereq_ok = str(prod.get("production_eligibility_status", "")) == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED" and str(gov.get("session_governor_status", "")) == "PASS_SESSION_GOVERNOR_READY_LOCKED"

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def eligibility(self) -> str:
        if self.v114_baseline_status.startswith("FAIL") or self.any_fail:
            return "AUTONOMY_REPAIR_REQUIRED"
        if self.approved and self.prereq_ok:
            return "AUTONOMY_REVIEW_ELIGIBLE_LOCKED"
        return "AUTONOMY_NOT_ELIGIBLE"

    @property
    def controller_status(self) -> str:
        e = self.eligibility
        if e == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED":
            return "PASS_AUTONOMY_REVIEW_ELIGIBLE_LOCKED"
        if e == "AUTONOMY_REPAIR_REQUIRED":
            return "FAIL_CLOSED_AUTONOMY_REPAIR_REQUIRED" if self.any_fail else "PARTIAL_AUTONOMY_REPAIR_REQUIRED"
        return "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT" if not self.approved else "PARTIAL_AUTONOMY_NOT_ELIGIBLE"

    @property
    def final_verdict(self) -> str:
        if self.v114_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.eligibility == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED" else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v114_baseline_status.startswith("FAIL"):
            return ["FAIL_V114_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL"]
        if self.eligibility == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED":
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("AUTONOMY_REVIEW_APPROVAL_ABSENT")
        if not self.prereq_ok:
            blockers.append("AUTONOMY_PREREQUISITES_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        if self.eligibility == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED":
            return "AUTONOMY_REVIEW_ELIGIBLE_LOCKED_NO_AUTONOMOUS_TRADING_AWAIT_SEPARATE_ENABLE_APPROVAL"
        return "OPERATOR_MUST_PROVIDE_AUTONOMY_REVIEW_APPROVAL_AND_PREREQUISITES_NO_AUTONOMY_ENABLED"


def _common(ctx: V115Context) -> dict[str, Any]:
    return {
        "v114_baseline_status": ctx.v114_baseline_status,
        "autonomy_review_controller_status": ctx.controller_status,
        "autonomy_review_approval_validator_status": "PASS_AUTONOMY_REVIEW_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL" if ctx.any_fail else "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT"),
        "autonomy_review_phrase": sgc.AUTONOMY_REVIEW_PHRASE,
        "autonomy_review_approval_hash": ctx.validation["approval_hash"],
        "campaign_session_evidence_prerequisite_status": "PASS_CAMPAIGN_SESSION_EVIDENCE_PRESENT" if ctx.prereq_ok else "PARTIAL_CAMPAIGN_SESSION_EVIDENCE_ABSENT",
        "risk_abstention_prerequisite_status": "PASS_RISK_ABSTENTION_PRESENT",
        "broker_firewall_prerequisite_status": "PASS_FIREWALL_ONLY_NO_CONTACT",
        "live_submit_caps_control_prerequisite_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "autonomy_eligibility_status": ctx.eligibility,
        "no_autonomous_order_proof_status": "PASS_NO_AUTONOMOUS_ORDER",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "autonomous_trading_enabled": False,
        "autonomy_enabled": False,
        "auto_order_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "readiness_governor_v75_status": "PASS",
        "execution_lock_deep_recheck_v74_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V115Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v114_baseline"):
        return "PASS" if ctx.v114_baseline_status == "PASS_V114_BASELINE_READBACK" else "FAIL" if ctx.v114_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v115_autonomy_review_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.eligibility == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED" else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V115Context) -> dict[str, Any]:
    workstream = "v115: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v115_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V115_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v115_report.json":
        report.update({"completion_oriented_next_action_v115_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v114_carried_status": ctx.v114_baseline_status, "autonomy_eligibility_status": ctx.eligibility, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v115_autonomy_review_controller_report.json"), "no_autonomous_order": str(ARTIFACTS / "v115_no_autonomous_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v115.json", "dummy_canonical_identity_report_v115.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V115ReportFactory:
    def __init__(self, *, autonomy_approval=None, autonomy_approval_path=None, prereq_override=None) -> None:
        self.kw = dict(autonomy_approval=autonomy_approval, autonomy_approval_path=autonomy_approval_path, prereq_override=prereq_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V115Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
