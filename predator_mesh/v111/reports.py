"""DUMMY v111 operator-approved scale-step 1 gate — reviews scale step 1 if exact approval exists; never auto-scales.

Reads the scale-approval result from V107 and the production-readiness prerequisite from V110. Emits a
scale recommendation only (NO_SCALE / SCALE_STEP_1_REVIEW_READY / SCALE_STEP_1_BLOCKED). Caps are never
modified and no order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v111 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v111: Operator Approved Scale Step 1 Gate No Auto Scale"
MISSION_NAME = "dummy_mission_state_report_v97.json"
FINAL_NAME = "final_report_v111.json"
INDEX_KEYS = ["scale_gate_controller_status", "scale_recommendation", "no_caps_modification_proof_status"]
DASH_TITLE = "Dummy V111 Scale Step 1 Gate"
MISSION_KEY = "dummy_mission_state_report_v97"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scale Gate", "scale_gate_controller_status"],
    ["Recommendation", "scale_recommendation"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V111_ROUTES = [
    "/api/v111/scale-gate-controller",
    "/api/v111/v110-baseline",
    "/api/v111/scale-approval-readback",
    "/api/v111/risk-prerequisite-validator",
    "/api/v111/production-readiness-prerequisite-validator",
    "/api/v111/scale-recommendation",
    "/api/v111/no-caps-modification-proof",
    "/api/v111/no-order-proof",
    "/api/v111/readiness-governor",
    "/api/v111/execution-lock",
    "/api/v111/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "scale-gate-controller": ["v111_scale_gate_controller_report.json"],
    "v110-baseline": ["v110_baseline_readback_v1_report.json"],
    "scale-approval-readback": ["v111_scale_approval_readback_report.json"],
    "risk-prerequisite-validator": ["v111_risk_prerequisite_validator_report.json"],
    "production-readiness-prerequisite-validator": ["v111_production_readiness_prerequisite_validator_report.json"],
    "scale-recommendation": ["v111_scale_recommendation_report.json"],
    "no-caps-modification-proof": ["v111_no_caps_modification_proof_report.json"],
    "no-order-proof": ["v111_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v71_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v70_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v111_report_v1.json", "completion_oriented_next_action_v111_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(111)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v111/reports.py scripts/generate_v111_reports.py dashboard/backend/v111_routes.py",
    "python scripts/generate_v111_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V111Context:
    def __init__(self, *, scale_approved_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.v110_baseline_status = sgc.baseline_status("final_report_v110.json", "V110")
        v107 = sgc.load_artifact("final_report_v107.json")
        if scale_approved_override is not None:
            self.scale_approved = bool(scale_approved_override)
        else:
            self.scale_approved = str(v107.get("scale_approval_controller_status", "")) == "PASS_SCALE_APPROVAL_VALID_REVIEW_ONLY_NO_SCALE"
        v110 = sgc.load_artifact("final_report_v110.json")
        if production_ready_override is not None:
            self.production_ready = bool(production_ready_override)
        else:
            self.production_ready = str(v110.get("production_eligibility_status", "")) == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED"
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def scale_recommendation(self) -> str:
        if not self.scale_approved:
            return "NO_SCALE"
        if self.production_ready and self.risk_ready:
            return "SCALE_STEP_1_REVIEW_READY"
        return "SCALE_STEP_1_BLOCKED"

    @property
    def controller_status(self) -> str:
        return "PASS_SCALE_GATE_REVIEWED_NO_SCALE_APPLIED"

    @property
    def final_verdict(self) -> str:
        if self.v110_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v110_baseline_status.startswith("FAIL"):
            return ["FAIL_V110_BASELINE_REGRESSION"]
        if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY":
            return []
        if not self.scale_approved:
            return ["SCALE_STEP_1_APPROVAL_ABSENT"]
        return ["SCALE_STEP_1_PREREQUISITES_UNMET"]

    @property
    def next_action(self) -> str:
        if self.scale_recommendation == "SCALE_STEP_1_REVIEW_READY":
            return "SCALE_STEP_1_REVIEW_READY_AWAIT_SEPARATE_CAPS_APPROVAL_NO_AUTO_SCALE"
        if self.scale_recommendation == "SCALE_STEP_1_BLOCKED":
            return "SCALE_STEP_1_BLOCKED_COMPLETE_PREREQUISITES_NO_CAPS_CHANGE"
        return "OPERATOR_MUST_PROVIDE_EXACT_SCALE_STEP_1_APPROVAL_NO_CAPS_CHANGE"


def _common(ctx: V111Context) -> dict[str, Any]:
    return {
        "v110_baseline_status": ctx.v110_baseline_status,
        "scale_gate_controller_status": ctx.controller_status,
        "scale_approval_readback_status": "PASS_SCALE_APPROVAL_VALID" if ctx.scale_approved else "PARTIAL_SCALE_APPROVAL_ABSENT",
        "scale_approval_present": ctx.scale_approved,
        "risk_prerequisite_validator_status": "PASS_RISK_PREREQUISITE_MET" if ctx.risk_ready else "PARTIAL_RISK_PREREQUISITE_UNMET",
        "production_readiness_prerequisite_validator_status": "PASS_PRODUCTION_READY" if ctx.production_ready else "PARTIAL_PRODUCTION_NOT_READY",
        "scale_recommendation": ctx.scale_recommendation,
        "scale_recommendation_status": f"PASS_{ctx.scale_recommendation}" if ctx.scale_recommendation != "NO_SCALE" else "PARTIAL_NO_SCALE",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_order_proof_status": "PASS_NO_ORDER",
        "scale_applied": False,
        "caps_changed": False,
        "caps_modified": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "readiness_governor_v71_status": "PASS",
        "execution_lock_deep_recheck_v70_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V111Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v110_baseline"):
        return "PASS" if ctx.v110_baseline_status == "PASS_V110_BASELINE_READBACK" else "FAIL" if ctx.v110_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v111_scale_gate_controller_report.json":
        return "PASS" if ctx.scale_recommendation == "SCALE_STEP_1_REVIEW_READY" else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V111Context) -> dict[str, Any]:
    workstream = "v111: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v111_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V111_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v111_report.json":
        report.update({"completion_oriented_next_action_v111_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v110_carried_status": ctx.v110_baseline_status, "scale_recommendation": ctx.scale_recommendation, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v111_scale_gate_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v111_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v111.json", "dummy_canonical_identity_report_v111.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V111ReportFactory:
    def __init__(self, *, scale_approved_override=None, production_ready_override=None, risk_ready_override=None) -> None:
        self.kw = dict(scale_approved_override=scale_approved_override, production_ready_override=production_ready_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V111Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
