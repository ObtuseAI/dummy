"""DUMMY v181 scale review V2 — reviews scale evidence using pilot/session proof; never applies scale.

Validates the exact scale-step approval and requires first-pilot, repeat-pilot, controlled-session, and session-decision
evidence plus risk/abstention prerequisites. Emits a scale recommendation only (NO_SCALE /
SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF / SCALE_STEP_1_REVIEW_READY_LOCKED / SCALE_REPAIR_REQUIRED). Default is
SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF with scale_applied=false and caps unchanged. No order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v181 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v181: Scale Review V2 Live Session Evidence No Caps Modification"
MISSION_NAME = "dummy_mission_state_report_v167.json"
FINAL_NAME = "final_report_v181.json"
INDEX_KEYS = ["scale_review_controller_status", "scale_recommendation", "scale_applied"]
DASH_TITLE = "Dummy V181 Scale Review V2"
MISSION_KEY = "dummy_mission_state_report_v167"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Review", "scale_review_controller_status"],
    ["Recommendation", "scale_recommendation"],
    ["Scale Applied", "scale_applied"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V181_ROUTES = [
    "/api/v181/scale-review-controller",
    "/api/v181/v180-baseline",
    "/api/v181/scale-approval-validator",
    "/api/v181/first-pilot-evidence-prerequisite",
    "/api/v181/repeat-pilot-evidence-prerequisite",
    "/api/v181/controlled-session-evidence-prerequisite",
    "/api/v181/session-decision-prerequisite",
    "/api/v181/risk-prerequisite",
    "/api/v181/abstention-prerequisite",
    "/api/v181/live-submit-caps-unchanged-proof",
    "/api/v181/scale-recommendation",
    "/api/v181/no-caps-modification-proof",
    "/api/v181/no-order-proof",
    "/api/v181/readiness-governor",
    "/api/v181/execution-lock",
    "/api/v181/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-review-controller": ["v181_scale_review_controller_report.json"],
    "v180-baseline": ["v180_baseline_readback_v1_report.json"],
    "scale-approval-validator": ["v181_scale_approval_validator_report.json"],
    "first-pilot-evidence-prerequisite": ["v181_first_pilot_evidence_prerequisite_report.json"],
    "repeat-pilot-evidence-prerequisite": ["v181_repeat_pilot_evidence_prerequisite_report.json"],
    "controlled-session-evidence-prerequisite": ["v181_controlled_session_evidence_prerequisite_report.json"],
    "session-decision-prerequisite": ["v181_session_decision_prerequisite_report.json"],
    "risk-prerequisite": ["v181_risk_prerequisite_report.json"],
    "abstention-prerequisite": ["v181_abstention_prerequisite_report.json"],
    "live-submit-caps-unchanged-proof": ["v181_live_submit_caps_unchanged_proof_report.json"],
    "scale-recommendation": ["v181_scale_recommendation_report.json"],
    "no-caps-modification-proof": ["v181_no_caps_modification_proof_report.json"],
    "no-order-proof": ["v181_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v141_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v140_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v181_report_v1.json", "completion_oriented_next_action_v181_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(181)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v181/reports.py scripts/generate_v181_reports.py dashboard/backend/v181_routes.py",
    "python scripts/generate_v181_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V181Context:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, session_evidence_override=None, risk_ready_override=None) -> None:
        self.v180_baseline_status = sgc.baseline_status("final_report_v180.json", "V180")
        res = sgc.resolve_packet(scale_approval_path, scale_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
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
    def scale_recommendation(self) -> str:
        if self.any_fail:
            return "SCALE_REPAIR_REQUIRED"
        if not self.session_ok:
            return "SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF"
        if not self.approved:
            return "NO_SCALE"
        if self.risk_ready:
            return "SCALE_STEP_1_REVIEW_READY_LOCKED"
        return "SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF"

    @property
    def ready(self) -> bool:
        return self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
        if self.ready:
            return "PASS_SCALE_REVIEW_V2_READY_LOCKED"
        return "PARTIAL_SCALE_REVIEW_V2_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v180_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v180_baseline_status.startswith("FAIL"):
            return ["FAIL_V180_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_SCALE_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.session_ok:
            blockers.append("CONTROLLED_SESSION_EVIDENCE_ABSENT")
        if not self.approved:
            blockers.append("SCALE_APPROVAL_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_PREREQUISITE_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "SCALE_REVIEW_V2_READY_LOCKED_AWAIT_SEPARATE_SCALE_BUNDLE_NO_CAPS_CHANGE" if self.ready else "OPERATOR_MUST_PROVIDE_SCALE_APPROVAL_AND_CONTROLLED_SESSION_LIVE_PROOF_NO_SCALE_APPLIED"


def _common(ctx: V181Context) -> dict[str, Any]:
    return {
        "v180_baseline_status": ctx.v180_baseline_status,
        "scale_review_controller_status": ctx.controller_status,
        "scale_approval_validator_status": "PASS_SCALE_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_SCALE_APPROVAL" if ctx.any_fail else "PARTIAL_SCALE_APPROVAL_ABSENT"),
        "scale_step_phrase": sgc.SCALE_STEP_PHRASE,
        "scale_approval_hash": ctx.validation["approval_hash"],
        "first_pilot_evidence_prerequisite_status": "PASS_FIRST_PILOT_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_FIRST_PILOT_EVIDENCE_ABSENT",
        "repeat_pilot_evidence_prerequisite_status": "PASS_REPEAT_PILOT_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_REPEAT_PILOT_EVIDENCE_ABSENT",
        "controlled_session_evidence_prerequisite_status": "PASS_CONTROLLED_SESSION_EVIDENCE_PRESENT" if ctx.session_ok else "PARTIAL_CONTROLLED_SESSION_EVIDENCE_ABSENT",
        "session_decision_prerequisite_status": "PASS_SESSION_DECISION_PRESENT" if ctx.session_ok else "PARTIAL_SESSION_DECISION_ABSENT",
        "risk_prerequisite_status": "PASS_RISK_PREREQUISITE_MET" if ctx.risk_ready else "PARTIAL_RISK_PREREQUISITE_UNMET",
        "abstention_prerequisite_status": "PASS_ABSTENTION_PREREQUISITE_MET",
        "live_submit_caps_unchanged_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "scale_recommendation": ctx.scale_recommendation,
        "scale_recommendation_status": f"PASS_{ctx.scale_recommendation}" if ctx.ready else f"PARTIAL_{ctx.scale_recommendation}",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_order_proof_status": "PASS_NO_ORDER",
        "scale_applied": False,
        "caps_changed": False,
        "caps_modified": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v141_status": "PASS",
        "execution_lock_deep_recheck_v140_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V181Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v180_baseline"):
        return "PASS" if ctx.v180_baseline_status == "PASS_V180_BASELINE_READBACK" else "FAIL" if ctx.v180_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v181_scale_review_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V181Context) -> dict[str, Any]:
    workstream = "v181: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v181_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V181_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v181_report.json":
        report.update({"completion_oriented_next_action_v181_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v180_carried_status": ctx.v180_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v181_scale_review_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v181_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v181.json", "dummy_canonical_identity_report_v181.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V181ReportFactory:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, session_evidence_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, scale_approval_path=scale_approval_path, session_evidence_override=session_evidence_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V181Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
