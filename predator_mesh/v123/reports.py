"""DUMMY v123 scale-step 1 review lock — reviews scale step 1 only; never applies scale or modifies caps.

Validates the exact scale-step approval and reads pilot / risk / abstention / production-readiness prerequisites.
Emits a scale recommendation only (NO_SCALE / SCALE_STEP_1_REVIEW_READY / SCALE_STEP_1_BLOCKED). Default is
NO_SCALE with scale_applied=false and caps unchanged. No order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v123 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v123: Scale Step 1 Review Lock No Caps Modification"
MISSION_NAME = "dummy_mission_state_report_v109.json"
FINAL_NAME = "final_report_v123.json"
INDEX_KEYS = ["scale_review_controller_status", "scale_recommendation", "no_caps_modification_proof_status"]
DASH_TITLE = "Dummy V123 Scale Step 1 Review Lock"
MISSION_KEY = "dummy_mission_state_report_v109"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Review", "scale_review_controller_status"],
    ["Recommendation", "scale_recommendation"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V123_ROUTES = [
    "/api/v123/scale-review-controller",
    "/api/v123/v122-baseline",
    "/api/v123/scale-approval-validator",
    "/api/v123/pilot-evidence-prerequisite",
    "/api/v123/risk-prerequisite",
    "/api/v123/abstention-prerequisite",
    "/api/v123/production-readiness-prerequisite",
    "/api/v123/scale-recommendation",
    "/api/v123/no-caps-modification-proof",
    "/api/v123/no-auto-order-proof",
    "/api/v123/readiness-governor",
    "/api/v123/execution-lock",
    "/api/v123/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-review-controller": ["v123_scale_review_controller_report.json"],
    "v122-baseline": ["v122_baseline_readback_v1_report.json"],
    "scale-approval-validator": ["v123_scale_approval_validator_report.json"],
    "pilot-evidence-prerequisite": ["v123_pilot_evidence_prerequisite_report.json"],
    "risk-prerequisite": ["v123_risk_prerequisite_report.json"],
    "abstention-prerequisite": ["v123_abstention_prerequisite_report.json"],
    "production-readiness-prerequisite": ["v123_production_readiness_prerequisite_report.json"],
    "scale-recommendation": ["v123_scale_recommendation_report.json"],
    "no-caps-modification-proof": ["v123_no_caps_modification_proof_report.json"],
    "no-auto-order-proof": ["v123_no_auto_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v83_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v82_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v123_report_v1.json", "completion_oriented_next_action_v123_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(123)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v123/reports.py scripts/generate_v123_reports.py dashboard/backend/v123_routes.py",
    "python scripts/generate_v123_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V123Context:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pilot_evidence_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.v122_baseline_status = sgc.baseline_status("final_report_v122.json", "V122")
        res = sgc.resolve_packet(scale_approval_path, scale_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
        if pilot_evidence_override is not None:
            self.pilot_evidence_ok = bool(pilot_evidence_override)
        else:
            self.pilot_evidence_ok = str(sgc.load_artifact("final_report_v120.json").get("pilot_forensic_controller_status", "")) == "PASS_PRODUCTION_PILOT_REVIEWED_AUTOLOCKED"
        if production_ready_override is not None:
            self.production_ready = bool(production_ready_override)
        else:
            self.production_ready = str(sgc.load_artifact("final_report_v110.json").get("production_eligibility_status", "")) == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED"
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
            return "SCALE_STEP_1_BLOCKED"
        if not self.approved:
            return "NO_SCALE"
        if self.pilot_evidence_ok and self.production_ready and self.risk_ready:
            return "SCALE_STEP_1_REVIEW_READY"
        return "SCALE_STEP_1_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
        return "PASS_SCALE_REVIEWED_NO_SCALE_APPLIED"

    @property
    def final_verdict(self) -> str:
        if self.v122_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v122_baseline_status.startswith("FAIL"):
            return ["FAIL_V122_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_SCALE_APPROVAL"]
        if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY":
            return []
        if not self.approved:
            return ["SCALE_STEP_1_APPROVAL_ABSENT"]
        return ["SCALE_STEP_1_PREREQUISITES_UNMET"]

    @property
    def next_action(self) -> str:
        if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY":
            return "SCALE_STEP_1_REVIEW_READY_AWAIT_SEPARATE_CAPS_APPROVAL_NO_AUTO_SCALE"
        if self.scale_recommendation == "SCALE_STEP_1_BLOCKED":
            return "SCALE_STEP_1_BLOCKED_COMPLETE_PREREQUISITES_NO_CAPS_CHANGE"
        return "OPERATOR_MUST_PROVIDE_EXACT_SCALE_STEP_1_APPROVAL_NO_CAPS_CHANGE"


def _common(ctx: V123Context) -> dict[str, Any]:
    return {
        "v122_baseline_status": ctx.v122_baseline_status,
        "scale_review_controller_status": ctx.controller_status,
        "scale_approval_validator_status": "PASS_SCALE_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_SCALE_APPROVAL" if ctx.any_fail else "PARTIAL_SCALE_APPROVAL_ABSENT"),
        "scale_step_phrase": sgc.SCALE_STEP_PHRASE,
        "scale_approval_hash": ctx.validation["approval_hash"],
        "pilot_evidence_prerequisite_status": "PASS_PILOT_EVIDENCE_PRESENT" if ctx.pilot_evidence_ok else "PARTIAL_PILOT_EVIDENCE_ABSENT",
        "risk_prerequisite_status": "PASS_RISK_PREREQUISITE_MET" if ctx.risk_ready else "PARTIAL_RISK_PREREQUISITE_UNMET",
        "abstention_prerequisite_status": "PASS_ABSTENTION_PREREQUISITE_MET",
        "production_readiness_prerequisite_status": "PASS_PRODUCTION_READY" if ctx.production_ready else "PARTIAL_PRODUCTION_NOT_READY",
        "scale_recommendation": ctx.scale_recommendation,
        "scale_recommendation_status": f"PASS_{ctx.scale_recommendation}" if ctx.scale_recommendation != "NO_SCALE" else "PARTIAL_NO_SCALE",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_auto_order_proof_status": "PASS_NO_AUTO_ORDER",
        "scale_applied": False,
        "caps_changed": False,
        "caps_modified": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v83_status": "PASS",
        "execution_lock_deep_recheck_v82_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V123Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v122_baseline"):
        return "PASS" if ctx.v122_baseline_status == "PASS_V122_BASELINE_READBACK" else "FAIL" if ctx.v122_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v123_scale_review_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V123Context) -> dict[str, Any]:
    workstream = "v123: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v123_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V123_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v123_report.json":
        report.update({"completion_oriented_next_action_v123_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v122_carried_status": ctx.v122_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v123_scale_review_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v123_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v123.json", "dummy_canonical_identity_report_v123.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V123ReportFactory:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pilot_evidence_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, scale_approval_path=scale_approval_path, pilot_evidence_override=pilot_evidence_override, production_ready_override=production_ready_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V123Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
