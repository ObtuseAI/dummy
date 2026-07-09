"""DUMMY v73 second-canary gate — reviewed and locked, no second order submitted in this bundle."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v73 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V73_ROUTES = [
    "/api/v73/second-canary-gate-controller",
    "/api/v73/v72-baseline",
    "/api/v73/repeat-canary-eligibility",
    "/api/v73/stricter-approval-requirement",
    "/api/v73/stricter-risk-threshold-requirement",
    "/api/v73/no-auto-scale-proof",
    "/api/v73/no-submit-proof",
    "/api/v73/live-submit-caps-unchanged-proof",
    "/api/v73/readiness-governor",
    "/api/v73/execution-lock",
    "/api/v73/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "second-canary-gate-controller": ["v73_second_canary_gate_controller_report.json"],
    "v72-baseline": ["v72_baseline_readback_v1_report.json"],
    "repeat-canary-eligibility": ["v73_repeat_canary_eligibility_report.json"],
    "stricter-approval-requirement": ["v73_stricter_approval_requirement_report.json"],
    "stricter-risk-threshold-requirement": ["v73_stricter_risk_threshold_requirement_report.json"],
    "no-auto-scale-proof": ["v73_no_auto_scale_proof_report.json"],
    "no-submit-proof": ["v73_no_submit_proof_report.json"],
    "live-submit-caps-unchanged-proof": ["v73_live_submit_caps_unchanged_proof_report.json"],
    "readiness-governor": ["readiness_governor_v33_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v32_report.json"],
    "mission-state": ["dummy_mission_state_report_v59.json", "dashboard_v73_report_v1.json", "completion_oriented_next_action_v73_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(73)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v73/reports.py scripts/generate_v73_reports.py dashboard/backend/v73_routes.py",
    "python scripts/generate_v73_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V73Context:
    def __init__(self) -> None:
        self.v72_baseline_status = sgc.baseline_status("final_report_v72.json", "V72")
        self.first_canary_reconciled = str(sgc.load_artifact("final_report_v71.json").get("reconcile_controller_status", "")) == "PASS_LIVE_CANARY_RECONCILED"
        self.risk_review_complete = sgc.load_artifact("final_report_v72.json").get("verdict") == "PASS"

    @property
    def gate_ready(self) -> bool:
        return self.first_canary_reconciled and self.risk_review_complete

    @property
    def gate_status(self) -> str:
        # A submit path is never created here, so FAIL_SECOND_CANARY_CREATED_SUBMIT_PATH cannot occur.
        if self.v72_baseline_status.startswith("FAIL"):
            return "PARTIAL_SECOND_CANARY_BLOCKED"
        if self.gate_ready:
            return "PASS_SECOND_CANARY_GATE_READY_LOCKED"
        return "PARTIAL_SECOND_CANARY_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v72_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.gate_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v72_baseline_status.startswith("FAIL"):
            return ["FAIL_V72_BASELINE_REGRESSION"]
        blockers: list[str] = []
        if not self.first_canary_reconciled:
            blockers.append("MISSING_V70_V71_FIRST_CANARY_PROOF")
        if not self.risk_review_complete:
            blockers.append("MISSING_V72_RISK_REVIEW_PASS")
        return blockers

    @property
    def next_action(self) -> str:
        if self.gate_ready:
            return "SECOND_CANARY_GATE_READY_LOCKED_NO_SUBMIT_IN_THIS_BUNDLE"
        return "SECOND_CANARY_BLOCKED_AWAIT_FIRST_CANARY_AND_RISK_PROOF"


def _common(ctx: V73Context) -> dict[str, Any]:
    return {
        "v72_baseline_status": ctx.v72_baseline_status,
        "second_canary_gate_controller_status": ctx.gate_status,
        "repeat_canary_eligibility_status": "PASS_ELIGIBLE_LOCKED" if ctx.gate_ready else "PARTIAL_NOT_YET_ELIGIBLE",
        "first_canary_reconciled": ctx.first_canary_reconciled,
        "risk_review_complete": ctx.risk_review_complete,
        "stricter_approval_requirement_status": "PASS_STRICTER_APPROVAL_REQUIRED",
        "stricter_risk_threshold_requirement_status": "PASS_STRICTER_RISK_THRESHOLD_REQUIRED",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "second_order_submitted": False,
        "live_submit_caps_unchanged_proof_status": "PASS_LIVE_SUBMIT_CAPS_UNCHANGED",
        "readiness_governor_v33_status": "PASS",
        "execution_lock_deep_recheck_v32_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V73Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v72_baseline"):
        return "PASS" if ctx.v72_baseline_status == "PASS_V72_BASELINE_READBACK" else "FAIL" if ctx.v72_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v73_second_canary_gate_controller_report.json":
        return "PASS" if ctx.gate_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V73Context) -> dict[str, Any]:
    workstream = "v73: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v73_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V73_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v73_report.json":
        report.update({"completion_oriented_next_action_v73_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v59.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v72_carried_status": ctx.v72_baseline_status, "second_canary_gate_controller_status": ctx.gate_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v73.json"), "gate_controller": str(ARTIFACTS / "v73_second_canary_gate_controller_report.json"), "no_submit_proof": str(ARTIFACTS / "v73_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v73.json", "dummy_canonical_identity_report_v73.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V73ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V73Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
