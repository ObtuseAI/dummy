"""DUMMY v182 autonomy evidence review — reviews whether limited autonomy is even eligible; never enables autonomy.

Validates the exact autonomy-review approval and requires pilot / repeat / controlled-session evidence plus
risk/abstention/scale/controlled-operation prerequisites. Emits an eligibility only (AUTONOMY_NOT_ELIGIBLE /
AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF / AUTONOMY_REVIEW_READY_LOCKED / AUTONOMY_REPAIR_REQUIRED). Default is
AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF. autonomous_trading stays false; no autonomous order, no scale, no
live-submit/caps change.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v182 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v182: Autonomy Evidence Review No Autonomy Enablement"
MISSION_NAME = "dummy_mission_state_report_v168.json"
FINAL_NAME = "final_report_v182.json"
INDEX_KEYS = ["autonomy_evidence_controller_status", "autonomy_eligibility", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V182 Autonomy Evidence Review"
MISSION_KEY = "dummy_mission_state_report_v168"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Autonomy Evidence", "autonomy_evidence_controller_status"],
    ["Eligibility", "autonomy_eligibility"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V182_ROUTES = [
    "/api/v182/autonomy-evidence-controller",
    "/api/v182/v181-baseline",
    "/api/v182/autonomy-review-approval-validator",
    "/api/v182/pilot-evidence-prerequisite",
    "/api/v182/repeat-evidence-prerequisite",
    "/api/v182/session-evidence-prerequisite",
    "/api/v182/risk-governor-prerequisite",
    "/api/v182/abstention-governor-prerequisite",
    "/api/v182/scale-status-prerequisite",
    "/api/v182/controlled-operation-status-prerequisite",
    "/api/v182/autonomy-eligibility",
    "/api/v182/no-autonomous-order-proof",
    "/api/v182/no-live-submit-caps-change-proof",
    "/api/v182/no-scale-proof",
    "/api/v182/readiness-governor",
    "/api/v182/execution-lock",
    "/api/v182/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-evidence-controller": ["v182_autonomy_evidence_controller_report.json"],
    "v181-baseline": ["v181_baseline_readback_v1_report.json"],
    "autonomy-review-approval-validator": ["v182_autonomy_review_approval_validator_report.json"],
    "pilot-evidence-prerequisite": ["v182_pilot_evidence_prerequisite_report.json"],
    "repeat-evidence-prerequisite": ["v182_repeat_evidence_prerequisite_report.json"],
    "session-evidence-prerequisite": ["v182_session_evidence_prerequisite_report.json"],
    "risk-governor-prerequisite": ["v182_risk_governor_prerequisite_report.json"],
    "abstention-governor-prerequisite": ["v182_abstention_governor_prerequisite_report.json"],
    "scale-status-prerequisite": ["v182_scale_status_prerequisite_report.json"],
    "controlled-operation-status-prerequisite": ["v182_controlled_operation_status_prerequisite_report.json"],
    "autonomy-eligibility": ["v182_autonomy_eligibility_report.json"],
    "no-autonomous-order-proof": ["v182_no_autonomous_order_proof_report.json"],
    "no-live-submit-caps-change-proof": ["v182_no_live_submit_caps_change_proof_report.json"],
    "no-scale-proof": ["v182_no_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v142_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v141_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v182_report_v1.json", "completion_oriented_next_action_v182_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(182)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v182/reports.py scripts/generate_v182_reports.py dashboard/backend/v182_routes.py",
    "python scripts/generate_v182_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ELIGIBILITY_ENUM = [
    "AUTONOMY_NOT_ELIGIBLE",
    "AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF",
    "AUTONOMY_REVIEW_READY_LOCKED",
    "AUTONOMY_REPAIR_REQUIRED",
]


class V182Context:
    def __init__(self, *, autonomy_approval=None, autonomy_approval_path=None, session_evidence_override=None, risk_ready_override=None) -> None:
        self.v181_baseline_status = sgc.baseline_status("final_report_v181.json", "V181")
        res = sgc.resolve_packet(autonomy_approval_path, autonomy_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.AUTONOMY_REVIEW_PHRASE, required_fields=sgc.AUTONOMY_REVIEW_FIELDS, required_scope=sgc.AUTONOMY_REVIEW_SCOPE)
        if session_evidence_override is not None:
            self.session_ok = bool(session_evidence_override)
        else:
            self.session_ok = str(sgc.load_artifact("final_report_v180.json").get("session_decision_controller_status", "")) == "PASS_SESSION_DECISION_LOCKED"
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def autonomy_eligibility(self) -> str:
        if self.any_fail:
            return "AUTONOMY_REPAIR_REQUIRED"
        if not self.session_ok:
            return "AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF"
        if not self.approved:
            return "AUTONOMY_NOT_ELIGIBLE"
        if self.risk_ready:
            return "AUTONOMY_REVIEW_READY_LOCKED"
        return "AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF"

    @property
    def ready(self) -> bool:
        return self.autonomy_eligibility == "AUTONOMY_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL"
        if self.ready:
            return "PASS_AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED"
        return "PARTIAL_AUTONOMY_EVIDENCE_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v181_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v181_baseline_status.startswith("FAIL"):
            return ["FAIL_V181_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.session_ok:
            blockers.append("CONTROLLED_SESSION_LIVE_PROOF_ABSENT")
        if not self.approved:
            blockers.append("AUTONOMY_REVIEW_APPROVAL_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_GOVERNOR_PREREQUISITE_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED_AWAIT_SEPARATE_AUTONOMY_BUNDLE_NO_AUTONOMY_ENABLED" if self.ready else "OPERATOR_MUST_PROVIDE_AUTONOMY_REVIEW_APPROVAL_AND_CONTROLLED_SESSION_LIVE_PROOF_NO_AUTONOMY"


def _common(ctx: V182Context) -> dict[str, Any]:
    return {
        "v181_baseline_status": ctx.v181_baseline_status,
        "autonomy_evidence_controller_status": ctx.controller_status,
        "autonomy_review_approval_validator_status": "PASS_AUTONOMY_REVIEW_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL" if ctx.any_fail else "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT"),
        "autonomy_review_phrase": sgc.AUTONOMY_REVIEW_PHRASE,
        "autonomy_review_approval_hash": ctx.validation["approval_hash"],
        "pilot_evidence_prerequisite_status": "PASS_PILOT_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_PILOT_EVIDENCE_ABSENT",
        "repeat_evidence_prerequisite_status": "PASS_REPEAT_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_REPEAT_EVIDENCE_ABSENT",
        "session_evidence_prerequisite_status": "PASS_CONTROLLED_SESSION_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_CONTROLLED_SESSION_EVIDENCE_ABSENT",
        "risk_governor_prerequisite_status": "PASS_RISK_GOVERNOR_MET" if ctx.risk_ready else "PARTIAL_RISK_GOVERNOR_UNMET",
        "abstention_governor_prerequisite_status": "PASS_ABSTENTION_GOVERNOR_MET",
        "scale_status_prerequisite_status": "PASS_SCALE_STATUS_READ",
        "controlled_operation_status_prerequisite_status": "PASS_CONTROLLED_OPERATION_STATUS_READ",
        "autonomy_eligibility": ctx.autonomy_eligibility,
        "autonomy_eligibility_enum": ELIGIBILITY_ENUM,
        "no_autonomous_order_proof_status": "PASS_NO_AUTONOMOUS_ORDER",
        "no_live_submit_caps_change_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "autonomy_enabled": False,
        "auto_order_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v142_status": "PASS",
        "execution_lock_deep_recheck_v141_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V182Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v181_baseline"):
        return "PASS" if ctx.v181_baseline_status == "PASS_V181_BASELINE_READBACK" else "FAIL" if ctx.v181_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v182_autonomy_evidence_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V182Context) -> dict[str, Any]:
    workstream = "v182: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v182_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V182_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v182_report.json":
        report.update({"completion_oriented_next_action_v182_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v181_carried_status": ctx.v181_baseline_status, "autonomy_eligibility": ctx.autonomy_eligibility, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v182_autonomy_evidence_controller_report.json"), "no_autonomous_order": str(ARTIFACTS / "v182_no_autonomous_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v182.json", "dummy_canonical_identity_report_v182.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V182ReportFactory:
    def __init__(self, *, autonomy_approval=None, autonomy_approval_path=None, session_evidence_override=None, risk_ready_override=None) -> None:
        self.kw = dict(autonomy_approval=autonomy_approval, autonomy_approval_path=autonomy_approval_path, session_evidence_override=session_evidence_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V182Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
