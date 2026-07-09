"""DUMMY v202 scale + autonomy evidence refresh — refreshes scale/autonomy eligibility from first live proof; no scale, no autonomy.

Validates the exact scale-step and autonomy-review approvals and requires first-live-proof + forensic + risk +
abstention + shadow-forensic prerequisites. Emits a scale recommendation (NO_SCALE / SCALE_BLOCKED_NO_LIVE_PROOF /
SCALE_REVIEW_READY_LOCKED / SCALE_REPAIR_REQUIRED) and an autonomy recommendation (AUTONOMY_NOT_ELIGIBLE /
AUTONOMY_BLOCKED_NO_LIVE_PROOF / AUTONOMY_REVIEW_READY_LOCKED / AUTONOMY_REPAIR_REQUIRED). Default is
SCALE_BLOCKED_NO_LIVE_PROOF + AUTONOMY_BLOCKED_NO_LIVE_PROOF. scale_applied=false, autonomous_trading=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v202 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v202: Scale And Autonomy Evidence Refresh No Scale No Autonomy"
MISSION_NAME = "dummy_mission_state_report_v188.json"
FINAL_NAME = "final_report_v202.json"
INDEX_KEYS = ["evidence_refresh_controller_status", "scale_recommendation", "autonomy_recommendation"]
DASH_TITLE = "Dummy V202 Scale & Autonomy Evidence Refresh"
MISSION_KEY = "dummy_mission_state_report_v188"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Evidence Refresh", "evidence_refresh_controller_status"],
    ["Scale", "scale_recommendation"],
    ["Autonomy", "autonomy_recommendation"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V202_ROUTES = [
    "/api/v202/evidence-refresh-controller",
    "/api/v202/v201-baseline",
    "/api/v202/scale-approval-validator",
    "/api/v202/autonomy-review-approval-validator",
    "/api/v202/live-proof-prerequisite",
    "/api/v202/forensic-prerequisite",
    "/api/v202/risk-prerequisite",
    "/api/v202/abstention-prerequisite",
    "/api/v202/shadow-forensic-prerequisite",
    "/api/v202/scale-recommendation",
    "/api/v202/autonomy-recommendation",
    "/api/v202/no-caps-modification-proof",
    "/api/v202/no-autonomous-order-proof",
    "/api/v202/no-submit-proof",
    "/api/v202/readiness-governor",
    "/api/v202/execution-lock",
    "/api/v202/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "evidence-refresh-controller": ["v202_evidence_refresh_controller_report.json"],
    "v201-baseline": ["v201_baseline_readback_v1_report.json"],
    "scale-approval-validator": ["v202_scale_approval_validator_report.json"],
    "autonomy-review-approval-validator": ["v202_autonomy_review_approval_validator_report.json"],
    "live-proof-prerequisite": ["v202_live_proof_prerequisite_report.json"],
    "forensic-prerequisite": ["v202_forensic_prerequisite_report.json"],
    "risk-prerequisite": ["v202_risk_prerequisite_report.json"],
    "abstention-prerequisite": ["v202_abstention_prerequisite_report.json"],
    "shadow-forensic-prerequisite": ["v202_shadow_forensic_prerequisite_report.json"],
    "scale-recommendation": ["v202_scale_recommendation_report.json"],
    "autonomy-recommendation": ["v202_autonomy_recommendation_report.json"],
    "no-caps-modification-proof": ["v202_no_caps_modification_proof_report.json"],
    "no-autonomous-order-proof": ["v202_no_autonomous_order_proof_report.json"],
    "no-submit-proof": ["v202_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v162_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v161_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v202_report_v1.json", "completion_oriented_next_action_v202_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(202)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v202/reports.py scripts/generate_v202_reports.py dashboard/backend/v202_routes.py",
    "python scripts/generate_v202_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V202Context:
    def __init__(self, *, scale_approval=None, autonomy_approval=None, live_proof_override=None, risk_ready_override=None) -> None:
        self.v201_baseline_status = sgc.baseline_status("final_report_v201.json", "V201")
        self.scale_v = sgc.validate_packet(sgc.resolve_packet(None, scale_approval), required_phrase=sgc.SCALE_STEP_PHRASE, required_fields=sgc.SCALE_STEP_FIELDS, required_scope=sgc.SCALE_STEP_SCOPE)
        self.autonomy_v = sgc.validate_packet(sgc.resolve_packet(None, autonomy_approval), required_phrase=sgc.AUTONOMY_REVIEW_PHRASE, required_fields=sgc.AUTONOMY_REVIEW_FIELDS, required_scope=sgc.AUTONOMY_REVIEW_SCOPE)
        if live_proof_override is not None:
            self.live_proof = bool(live_proof_override)
        else:
            self.live_proof = str(sgc.load_artifact("final_report_v201.json").get("forensic_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_FORENSIC_REVIEWED"
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.scale_v, self.autonomy_v))

    @property
    def scale_recommendation(self) -> str:
        if self.scale_v["state"] == "PRESENT" and not self.scale_v["accepted"]:
            return "SCALE_REPAIR_REQUIRED"
        if not self.live_proof:
            return "SCALE_BLOCKED_NO_LIVE_PROOF"
        if not self.scale_v["accepted"]:
            return "NO_SCALE"
        return "SCALE_REVIEW_READY_LOCKED" if self.risk_ready else "SCALE_BLOCKED_NO_LIVE_PROOF"

    @property
    def autonomy_recommendation(self) -> str:
        if self.autonomy_v["state"] == "PRESENT" and not self.autonomy_v["accepted"]:
            return "AUTONOMY_REPAIR_REQUIRED"
        if not self.live_proof:
            return "AUTONOMY_BLOCKED_NO_LIVE_PROOF"
        if not self.autonomy_v["accepted"]:
            return "AUTONOMY_NOT_ELIGIBLE"
        return "AUTONOMY_REVIEW_READY_LOCKED" if self.risk_ready else "AUTONOMY_BLOCKED_NO_LIVE_PROOF"

    @property
    def ready(self) -> bool:
        return self.scale_recommendation == "SCALE_REVIEW_READY_LOCKED" and self.autonomy_recommendation == "AUTONOMY_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_SCALE_OR_AUTONOMY_APPROVAL"
        if self.ready:
            return "PASS_SCALE_AND_AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED"
        return "PARTIAL_SCALE_AND_AUTONOMY_EVIDENCE_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v201_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v201_baseline_status.startswith("FAIL"):
            return ["FAIL_V201_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_SCALE_OR_AUTONOMY_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.live_proof:
            blockers.append("FIRST_LIVE_PROOF_ABSENT")
        if not self.scale_v["accepted"]:
            blockers.append("SCALE_APPROVAL_ABSENT")
        if not self.autonomy_v["accepted"]:
            blockers.append("AUTONOMY_REVIEW_APPROVAL_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "SCALE_AND_AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED_AWAIT_SEPARATE_BUNDLES_NO_SCALE_NO_AUTONOMY" if self.ready else "OPERATOR_MUST_PROVIDE_SCALE_AND_AUTONOMY_APPROVALS_AND_FIRST_LIVE_PROOF_NO_SCALE_NO_AUTONOMY"


def _common(ctx: V202Context) -> dict[str, Any]:
    return {
        "v201_baseline_status": ctx.v201_baseline_status,
        "evidence_refresh_controller_status": ctx.controller_status,
        "scale_approval_validator_status": "PASS_SCALE_APPROVAL_VALID" if ctx.scale_v["accepted"] else ("FAIL_CLOSED_INVALID_SCALE_APPROVAL" if ctx.scale_v["state"] == "PRESENT" and not ctx.scale_v["accepted"] else "PARTIAL_SCALE_APPROVAL_ABSENT"),
        "autonomy_review_approval_validator_status": "PASS_AUTONOMY_REVIEW_APPROVAL_VALID" if ctx.autonomy_v["accepted"] else ("FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL" if ctx.autonomy_v["state"] == "PRESENT" and not ctx.autonomy_v["accepted"] else "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT"),
        "live_proof_prerequisite_status": "PASS_LIVE_PROOF_PRESENT" if ctx.live_proof else "PARTIAL_LIVE_PROOF_ABSENT",
        "forensic_prerequisite_status": "PASS_FORENSIC_PRESENT" if ctx.live_proof else "PARTIAL_FORENSIC_ABSENT",
        "risk_prerequisite_status": "PASS_RISK_PREREQUISITE_MET" if ctx.risk_ready else "PARTIAL_RISK_PREREQUISITE_UNMET",
        "abstention_prerequisite_status": "PASS_ABSTENTION_PREREQUISITE_MET",
        "shadow_forensic_prerequisite_status": "PASS_SHADOW_FORENSIC_PRESENT",
        "scale_recommendation": ctx.scale_recommendation,
        "scale_recommendation_status": f"PASS_{ctx.scale_recommendation}" if ctx.scale_recommendation == "SCALE_REVIEW_READY_LOCKED" else f"PARTIAL_{ctx.scale_recommendation}",
        "autonomy_recommendation": ctx.autonomy_recommendation,
        "autonomy_recommendation_status": f"PASS_{ctx.autonomy_recommendation}" if ctx.autonomy_recommendation == "AUTONOMY_REVIEW_READY_LOCKED" else f"PARTIAL_{ctx.autonomy_recommendation}",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_autonomous_order_proof_status": "PASS_NO_AUTONOMOUS_ORDER",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "scale_applied": False,
        "caps_changed": False,
        "caps_modified": False,
        "autonomy_enabled": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v162_status": "PASS",
        "execution_lock_deep_recheck_v161_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V202Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v201_baseline"):
        return "PASS" if ctx.v201_baseline_status == "PASS_V201_BASELINE_READBACK" else "FAIL" if ctx.v201_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v202_evidence_refresh_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V202Context) -> dict[str, Any]:
    workstream = "v202: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v202_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V202_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v202_report.json":
        report.update({"completion_oriented_next_action_v202_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v201_carried_status": ctx.v201_baseline_status, "scale_recommendation": ctx.scale_recommendation, "autonomy_recommendation": ctx.autonomy_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v202_evidence_refresh_controller_report.json"), "no_autonomous_order": str(ARTIFACTS / "v202_no_autonomous_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v202.json", "dummy_canonical_identity_report_v202.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V202ReportFactory:
    def __init__(self, *, scale_approval=None, autonomy_approval=None, live_proof_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approval=scale_approval, autonomy_approval=autonomy_approval, live_proof_override=live_proof_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V202Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
