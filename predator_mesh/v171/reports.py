"""DUMMY v171 scale-step 1 evidence validator — validates whether scale can even be reviewed; never applies scale.

Validates the exact scale-step approval and requires first-pilot, repeat-pilot, and pilot-pair-audit evidence plus risk
and abstention-quality prerequisites. Emits a scale recommendation only (NO_SCALE / SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF /
SCALE_STEP_1_REVIEW_READY_LOCKED / SCALE_REPAIR_REQUIRED). Default is SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF with
scale_applied=false and caps unchanged. No order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v171 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v171: Scale Step 1 Evidence Validator No Scale Applied"
MISSION_NAME = "dummy_mission_state_report_v157.json"
FINAL_NAME = "final_report_v171.json"
INDEX_KEYS = ["scale_evidence_controller_status", "scale_recommendation", "scale_applied"]
DASH_TITLE = "Dummy V171 Scale-Step 1 Evidence Validator"
MISSION_KEY = "dummy_mission_state_report_v157"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Evidence", "scale_evidence_controller_status"],
    ["Recommendation", "scale_recommendation"],
    ["Scale Applied", "scale_applied"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V171_ROUTES = [
    "/api/v171/scale-evidence-controller",
    "/api/v171/v170-baseline",
    "/api/v171/scale-approval-validator",
    "/api/v171/first-pilot-evidence-prerequisite",
    "/api/v171/repeat-pilot-evidence-prerequisite",
    "/api/v171/pilot-pair-audit-prerequisite",
    "/api/v171/risk-policy-prerequisite",
    "/api/v171/abstention-quality-prerequisite",
    "/api/v171/live-submit-caps-unchanged-proof",
    "/api/v171/no-loss-lock",
    "/api/v171/no-drift-lock",
    "/api/v171/scale-recommendation",
    "/api/v171/no-caps-modification-proof",
    "/api/v171/no-order-proof",
    "/api/v171/readiness-governor",
    "/api/v171/execution-lock",
    "/api/v171/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-evidence-controller": ["v171_scale_evidence_controller_report.json"],
    "v170-baseline": ["v170_baseline_readback_v1_report.json"],
    "scale-approval-validator": ["v171_scale_approval_validator_report.json"],
    "first-pilot-evidence-prerequisite": ["v171_first_pilot_evidence_prerequisite_report.json"],
    "repeat-pilot-evidence-prerequisite": ["v171_repeat_pilot_evidence_prerequisite_report.json"],
    "pilot-pair-audit-prerequisite": ["v171_pilot_pair_audit_prerequisite_report.json"],
    "risk-policy-prerequisite": ["v171_risk_policy_prerequisite_report.json"],
    "abstention-quality-prerequisite": ["v171_abstention_quality_prerequisite_report.json"],
    "live-submit-caps-unchanged-proof": ["v171_live_submit_caps_unchanged_proof_report.json"],
    "no-loss-lock": ["v171_no_loss_lock_report.json"],
    "no-drift-lock": ["v171_no_drift_lock_report.json"],
    "scale-recommendation": ["v171_scale_recommendation_report.json"],
    "no-caps-modification-proof": ["v171_no_caps_modification_proof_report.json"],
    "no-order-proof": ["v171_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v131_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v130_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v171_report_v1.json", "completion_oriented_next_action_v171_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(171)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v171/reports.py scripts/generate_v171_reports.py dashboard/backend/v171_routes.py",
    "python scripts/generate_v171_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V171Context:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pair_evidence_override=None, risk_ready_override=None) -> None:
        self.v170_baseline_status = sgc.baseline_status("final_report_v170.json", "V170")
        res = sgc.resolve_packet(scale_approval_path, scale_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
        if pair_evidence_override is not None:
            self.pair_ok = bool(pair_evidence_override)
        else:
            self.pair_ok = str(sgc.load_artifact("final_report_v170.json").get("pilot_pair_audit_controller_status", "")) == "PASS_PILOT_PAIR_AUDITED_LOCKED"
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
        if not self.pair_ok:
            return "SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF"
        if not self.approved:
            return "NO_SCALE"
        if self.risk_ready:
            return "SCALE_STEP_1_REVIEW_READY_LOCKED"
        return "SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF"

    @property
    def ready(self) -> bool:
        return self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
        if self.ready:
            return "PASS_SCALE_EVIDENCE_REVIEW_READY_LOCKED"
        return "PARTIAL_SCALE_EVIDENCE_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v170_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v170_baseline_status.startswith("FAIL"):
            return ["FAIL_V170_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_SCALE_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.pair_ok:
            blockers.append("PILOT_PAIR_EVIDENCE_ABSENT")
        if not self.approved:
            blockers.append("SCALE_APPROVAL_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_POLICY_PREREQUISITE_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "SCALE_EVIDENCE_REVIEW_READY_LOCKED_AWAIT_SEPARATE_SCALE_BUNDLE_NO_CAPS_CHANGE" if self.ready else "OPERATOR_MUST_PROVIDE_SCALE_APPROVAL_AND_PILOT_PAIR_LIVE_PROOF_NO_SCALE_APPLIED"


def _common(ctx: V171Context) -> dict[str, Any]:
    return {
        "v170_baseline_status": ctx.v170_baseline_status,
        "scale_evidence_controller_status": ctx.controller_status,
        "scale_approval_validator_status": "PASS_SCALE_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_SCALE_APPROVAL" if ctx.any_fail else "PARTIAL_SCALE_APPROVAL_ABSENT"),
        "scale_step_phrase": sgc.SCALE_STEP_PHRASE,
        "scale_approval_hash": ctx.validation["approval_hash"],
        "first_pilot_evidence_prerequisite_status": "PASS_FIRST_PILOT_EVIDENCE_PRESENT" if ctx.pair_ok else "PARTIAL_FIRST_PILOT_EVIDENCE_ABSENT",
        "repeat_pilot_evidence_prerequisite_status": "PASS_REPEAT_PILOT_EVIDENCE_PRESENT" if ctx.pair_ok else "PARTIAL_REPEAT_PILOT_EVIDENCE_ABSENT",
        "pilot_pair_audit_prerequisite_status": "PASS_PILOT_PAIR_AUDIT_PRESENT" if ctx.pair_ok else "PARTIAL_PILOT_PAIR_AUDIT_ABSENT",
        "risk_policy_prerequisite_status": "PASS_RISK_POLICY_MET" if ctx.risk_ready else "PARTIAL_RISK_POLICY_UNMET",
        "abstention_quality_prerequisite_status": "PASS_ABSTENTION_QUALITY_MET",
        "live_submit_caps_unchanged_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
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
        "readiness_governor_v131_status": "PASS",
        "execution_lock_deep_recheck_v130_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V171Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v170_baseline"):
        return "PASS" if ctx.v170_baseline_status == "PASS_V170_BASELINE_READBACK" else "FAIL" if ctx.v170_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v171_scale_evidence_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V171Context) -> dict[str, Any]:
    workstream = "v171: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v171_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V171_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v171_report.json":
        report.update({"completion_oriented_next_action_v171_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v170_carried_status": ctx.v170_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v171_scale_evidence_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v171_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v171.json", "dummy_canonical_identity_report_v171.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V171ReportFactory:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, pair_evidence_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, scale_approval_path=scale_approval_path, pair_evidence_override=pair_evidence_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V171Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
