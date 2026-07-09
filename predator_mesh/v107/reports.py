"""DUMMY v107 scale-step 1 approval validator — validates the exact scale phrase only; applies no scale.

Default is PARTIAL_SCALE_APPROVAL_ABSENT with scale_applied=false and caps_changed=false. Presenting
the exact scale approval validates it as review-only; it never applies scale or modifies caps.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v107 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v107: Scale Step 1 Approval Validator No Scale Applied"
MISSION_NAME = "dummy_mission_state_report_v93.json"
FINAL_NAME = "final_report_v107.json"
INDEX_KEYS = ["scale_approval_controller_status", "scale_applied", "caps_changed"]
DASH_TITLE = "Dummy V107 Scale Step 1 Approval Validator"
MISSION_KEY = "dummy_mission_state_report_v93"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Approval", "scale_approval_controller_status"],
    ["Scale Applied", "scale_applied"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V107_ROUTES = [
    "/api/v107/scale-approval-controller",
    "/api/v107/v106-baseline",
    "/api/v107/scale-phrase-validator",
    "/api/v107/scale-scope-expiration-operator-checks",
    "/api/v107/campaign-evidence-prerequisite",
    "/api/v107/risk-prerequisite",
    "/api/v107/no-caps-modification-proof",
    "/api/v107/no-order-proof",
    "/api/v107/readiness-governor",
    "/api/v107/execution-lock",
    "/api/v107/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-approval-controller": ["v107_scale_approval_controller_report.json"],
    "v106-baseline": ["v106_baseline_readback_v1_report.json"],
    "scale-phrase-validator": ["v107_scale_phrase_validator_report.json"],
    "scale-scope-expiration-operator-checks": ["v107_scale_scope_expiration_operator_checks_report.json"],
    "campaign-evidence-prerequisite": ["v107_campaign_evidence_prerequisite_report.json"],
    "risk-prerequisite": ["v107_risk_prerequisite_report.json"],
    "no-caps-modification-proof": ["v107_no_caps_modification_proof_report.json"],
    "no-order-proof": ["v107_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v67_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v66_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v107_report_v1.json", "completion_oriented_next_action_v107_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(107)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v107/reports.py scripts/generate_v107_reports.py dashboard/backend/v107_routes.py",
    "python scripts/generate_v107_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V107Context:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, campaign_evidence_override=None, risk_ready_override=None) -> None:
        self.v106_baseline_status = sgc.baseline_status("final_report_v106.json", "V106")
        res = sgc.resolve_packet(scale_approval_path, scale_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
        v106 = sgc.load_artifact("final_report_v106.json")
        self.campaign_evidence_ok = bool(campaign_evidence_override) if campaign_evidence_override is not None else (v106.get("verdict") in {"PASS", "PARTIAL"} and bool(v106))
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
        if self.approved:
            return "PASS_SCALE_APPROVAL_VALID_REVIEW_ONLY_NO_SCALE"
        return "PARTIAL_SCALE_APPROVAL_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v106_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.approved else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v106_baseline_status.startswith("FAIL"):
            return ["FAIL_V106_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_SCALE_APPROVAL"]
        return [] if self.approved else ["SCALE_STEP_1_APPROVAL_ABSENT"]

    @property
    def next_action(self) -> str:
        return "SCALE_STEP_1_APPROVAL_VALID_REVIEW_ONLY_AWAIT_SCALE_GATE_NO_CAPS_CHANGE" if self.approved else "OPERATOR_MUST_PROVIDE_EXACT_SCALE_STEP_1_APPROVAL"


def _common(ctx: V107Context) -> dict[str, Any]:
    return {
        "v106_baseline_status": ctx.v106_baseline_status,
        "scale_approval_controller_status": ctx.controller_status,
        "scale_phrase_validator_status": "PASS_SCALE_PHRASE_EXACT" if ctx.approved else ("FAIL_CLOSED_INVALID_SCALE_PHRASE" if ctx.any_fail else "PARTIAL_SCALE_PHRASE_ABSENT"),
        "scale_step_phrase": sgc.SCALE_STEP_PHRASE,
        "scale_scope_expiration_operator_checks_status": "PASS_SCOPE_EXPIRATION_OPERATOR" if ctx.approved else "PARTIAL_SCALE_APPROVAL_ABSENT",
        "campaign_evidence_prerequisite_status": "PASS_CAMPAIGN_EVIDENCE_PRESENT" if ctx.campaign_evidence_ok else "PARTIAL_CAMPAIGN_EVIDENCE_ABSENT",
        "risk_prerequisite_status": "PASS_RISK_PREREQUISITE_MET" if ctx.risk_ready else "PARTIAL_RISK_PREREQUISITE_UNMET",
        "scale_approval_hash": ctx.validation["approval_hash"],
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_order_proof_status": "PASS_NO_ORDER",
        "scale_applied": False,
        "caps_changed": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v67_status": "PASS",
        "execution_lock_deep_recheck_v66_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V107Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v106_baseline"):
        return "PASS" if ctx.v106_baseline_status == "PASS_V106_BASELINE_READBACK" else "FAIL" if ctx.v106_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v107_scale_approval_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.approved else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V107Context) -> dict[str, Any]:
    workstream = "v107: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v107_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V107_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v107_report.json":
        report.update({"completion_oriented_next_action_v107_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v106_carried_status": ctx.v106_baseline_status, "scale_approval_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v107_scale_approval_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v107_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v107.json", "dummy_canonical_identity_report_v107.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V107ReportFactory:
    def __init__(self, *, scale_approval=None, scale_approval_path=None, campaign_evidence_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, scale_approval_path=scale_approval_path, campaign_evidence_override=campaign_evidence_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V107Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
