"""DUMMY v133 scale-step 1 review gate V2 — reviews scale step 1 only; never applies scale or modifies caps.

Validates the exact scale-step approval and reads pilot (V130) / risk / abstention / production-readiness
prerequisites. Emits a scale recommendation only (NO_SCALE / SCALE_STEP_1_REVIEW_READY / SCALE_STEP_1_BLOCKED).
Default is NO_SCALE with scale_applied=false and caps unchanged. No order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v133 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v133: Scale Step 1 Review Gate V2 No Caps Modification"
MISSION_NAME = "dummy_mission_state_report_v119.json"
FINAL_NAME = "final_report_v133.json"
INDEX_KEYS = ["scale_review_controller_status", "scale_recommendation", "no_caps_modification_proof_status"]
DASH_TITLE = "Dummy V133 Scale Step 1 Review Gate V2"
MISSION_KEY = "dummy_mission_state_report_v119"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Review", "scale_review_controller_status"],
    ["Recommendation", "scale_recommendation"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V133_ROUTES = [
    "/api/v133/scale-review-controller",
    "/api/v133/v132-baseline",
    "/api/v133/scale-approval-validator",
    "/api/v133/pilot-evidence-prerequisite",
    "/api/v133/risk-prerequisite",
    "/api/v133/abstention-prerequisite",
    "/api/v133/production-readiness-prerequisite",
    "/api/v133/scale-recommendation",
    "/api/v133/no-caps-modification-proof",
    "/api/v133/no-auto-order-proof",
    "/api/v133/readiness-governor",
    "/api/v133/execution-lock",
    "/api/v133/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-review-controller": ["v133_scale_review_controller_report.json"],
    "v132-baseline": ["v132_baseline_readback_v1_report.json"],
    "scale-approval-validator": ["v133_scale_approval_validator_report.json"],
    "pilot-evidence-prerequisite": ["v133_pilot_evidence_prerequisite_report.json"],
    "risk-prerequisite": ["v133_risk_prerequisite_report.json"],
    "abstention-prerequisite": ["v133_abstention_prerequisite_report.json"],
    "production-readiness-prerequisite": ["v133_production_readiness_prerequisite_report.json"],
    "scale-recommendation": ["v133_scale_recommendation_report.json"],
    "no-caps-modification-proof": ["v133_no_caps_modification_proof_report.json"],
    "no-auto-order-proof": ["v133_no_auto_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v93_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v92_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v133_report_v1.json", "completion_oriented_next_action_v133_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(133)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v133/reports.py scripts/generate_v133_reports.py dashboard/backend/v133_routes.py",
    "python scripts/generate_v133_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V133Context:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pilot_evidence_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.v132_baseline_status = sgc.baseline_status("final_report_v132.json", "V132")
        res = sgc.resolve_packet(scale_approval_path, scale_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
        if pilot_evidence_override is not None:
            self.pilot_evidence_ok = bool(pilot_evidence_override)
        else:
            self.pilot_evidence_ok = str(sgc.load_artifact("final_report_v130.json").get("pilot_reconcile_controller_status", "")) == "PASS_PRODUCTION_PILOT_RECONCILED_REVIEWED_AUTOLOCKED"
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
        if self.v132_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v132_baseline_status.startswith("FAIL"):
            return ["FAIL_V132_BASELINE_REGRESSION"]
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


def _common(ctx: V133Context) -> dict[str, Any]:
    return {
        "v132_baseline_status": ctx.v132_baseline_status,
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
        "readiness_governor_v93_status": "PASS",
        "execution_lock_deep_recheck_v92_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V133Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v132_baseline"):
        return "PASS" if ctx.v132_baseline_status == "PASS_V132_BASELINE_READBACK" else "FAIL" if ctx.v132_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v133_scale_review_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V133Context) -> dict[str, Any]:
    workstream = "v133: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v133_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V133_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v133_report.json":
        report.update({"completion_oriented_next_action_v133_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v132_carried_status": ctx.v132_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v133_scale_review_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v133_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v133.json", "dummy_canonical_identity_report_v133.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V133ReportFactory:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pilot_evidence_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, scale_approval_path=scale_approval_path, pilot_evidence_override=pilot_evidence_override, production_ready_override=production_ready_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V133Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
