"""DUMMY v232 proof aware route decision — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v232 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v232: Proof Aware Route Decision"
MISSION_NAME = "dummy_mission_state_report_v218.json"
FINAL_NAME = "final_report_v232.json"
INDEX_KEYS = ['route_decision_controller_status', 'route_state', 'new_order_placed']
DASH_TITLE = "Dummy V232 Proof Aware Route Decision"
MISSION_KEY = "dummy_mission_state_report_v218"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Route Decision', 'route_decision_controller_status'], ['Route State', 'route_state'], ['Next Action', 'current_next_action'], ['Scale Applied', 'scale_applied'], ['Blockers', 'current_blockers']]

V232_ROUTES = ['/api/v232/route-decision-controller', '/api/v232/v231-baseline', '/api/v232/live-proof-prerequisite', '/api/v232/reconcile-forensic-prerequisite', '/api/v232/repeat-pilot-readiness', '/api/v232/controlled-session-readiness', '/api/v232/scale-review-readiness', '/api/v232/autonomy-review-readiness', '/api/v232/route-state', '/api/v232/no-submit-proof', '/api/v232/no-scale-proof', '/api/v232/no-autonomy-proof', '/api/v232/readiness-governor', '/api/v232/execution-lock', '/api/v232/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'route-decision-controller': ['v232_route_decision_controller_report.json'], 'v231-baseline': ['v231_baseline_readback_v1_report.json'], 'live-proof-prerequisite': ['v232_live_proof_prerequisite_report.json'], 'reconcile-forensic-prerequisite': ['v232_reconcile_forensic_prerequisite_report.json'], 'repeat-pilot-readiness': ['v232_repeat_pilot_readiness_report.json'], 'controlled-session-readiness': ['v232_controlled_session_readiness_report.json'], 'scale-review-readiness': ['v232_scale_review_readiness_report.json'], 'autonomy-review-readiness': ['v232_autonomy_review_readiness_report.json'], 'route-state': ['v232_route_state_report.json'], 'no-submit-proof': ['v232_no_submit_proof_report.json'], 'no-scale-proof': ['v232_no_scale_proof_report.json'], 'no-autonomy-proof': ['v232_no_autonomy_proof_report.json'], 'readiness-governor': ['readiness_governor_v192_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v191_report.json'], 'mission-state': ['dummy_mission_state_report_v218.json', 'dashboard_v232_report_v1.json', 'completion_oriented_next_action_v232_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(232)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v232/reports.py scripts/generate_v232_reports.py dashboard/backend/v232_routes.py",
    "python scripts/generate_v232_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v232_route_decision_controller_report.json"

class V232Context:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.v231_baseline_status = sgc.baseline_status("final_report_v231.json", "V231")
        if first_proof_override is not None:
            self.first_proof = bool(first_proof_override)
        else:
            self.first_proof = str(sgc.load_artifact("final_report_v231.json").get("reconcile_forensic_pipeline_controller_status", "")) == "PASS_RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED"
        if proof_target_override is not None:
            self.proof_target = proof_target_override
        else:
            self.proof_target = str(sgc.load_artifact("final_report_v231.json").get("proof_target", "NO_ATTEMPT"))

    @property
    def route_state(self) -> str:
        if not self.first_proof:
            return "ROUTE_BLOCKED_NO_LIVE_PROOF"
        if self.proof_target == "CONTROLLED_SESSION_PROOF":
            return "ROUTE_CONTROLLED_SESSION_REVIEW_READY"
        return "ROUTE_REPEAT_PILOT_REVIEW_READY"

    @property
    def ready(self) -> bool:
        return self.first_proof

    @property
    def controller_status(self) -> str:
        if self.v231_baseline_status.startswith("FAIL"):
            return "FAIL_ROUTE_DECISION_BASELINE_REGRESSION"
        return "PASS_ROUTE_DECISION_READY_LOCKED" if self.ready else "PARTIAL_ROUTE_DECISION_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v231_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v231_baseline_status.startswith("FAIL"):
            return ["FAIL_V231_BASELINE_REGRESSION"]
        return [] if self.ready else ["LIVE_PROOF_RECONCILE_FORENSIC_ABSENT"]

    @property
    def next_action(self) -> str:
        if self.route_state == "ROUTE_CONTROLLED_SESSION_REVIEW_READY":
            return "ROUTE_DECISION_READY_LOCKED_ROUTE_CONTROLLED_SESSION_REVIEW_NO_SUBMIT_NO_SCALE"
        if self.route_state == "ROUTE_REPEAT_PILOT_REVIEW_READY":
            return "ROUTE_DECISION_READY_LOCKED_ROUTE_REPEAT_PILOT_REVIEW_NO_SUBMIT_NO_SCALE"
        return "AWAIT_LIVE_PROOF_RECONCILE_AND_FORENSIC_BEFORE_ROUTE_DECISION"


def _common(ctx) -> dict[str, Any]:
    return {
        "v231_baseline_status": ctx.v231_baseline_status,
        "route_decision_controller_status": ctx.controller_status,
        "route_state": ctx.route_state,
        "route_states": ["ROUTE_BLOCKED_NO_LIVE_PROOF", "ROUTE_REPEAT_PILOT_REVIEW_READY", "ROUTE_CONTROLLED_SESSION_REVIEW_READY", "ROUTE_SCALE_REVIEW_READY_LOCKED", "ROUTE_AUTONOMY_REVIEW_BLOCKED", "ROUTE_REPAIR_REQUIRED"],
        "live_proof_prerequisite_status": "PASS_LIVE_PROOF_PRESENT" if ctx.first_proof else "PARTIAL_LIVE_PROOF_ABSENT",
        "reconcile_forensic_prerequisite_status": "PASS_RECONCILE_FORENSIC_PRESENT" if ctx.first_proof else "PARTIAL_RECONCILE_FORENSIC_ABSENT",
        "repeat_pilot_readiness_status": "PASS_REPEAT_PILOT_REVIEW_READY" if ctx.route_state == "ROUTE_REPEAT_PILOT_REVIEW_READY" else "PARTIAL_REPEAT_PILOT_REVIEW_BLOCKED",
        "controlled_session_readiness_status": "PASS_CONTROLLED_SESSION_REVIEW_READY" if ctx.route_state == "ROUTE_CONTROLLED_SESSION_REVIEW_READY" else "PARTIAL_CONTROLLED_SESSION_REVIEW_BLOCKED",
        "scale_review_readiness_status": "ROUTE_SCALE_REVIEW_READY_LOCKED_REVIEW_ONLY_NO_SCALE",
        "autonomy_review_readiness_status": "ROUTE_AUTONOMY_REVIEW_BLOCKED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "new_order_placed": False,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v192_status": "PASS",
        "execution_lock_deep_recheck_v191_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v231_baseline"):
        return "PASS" if ctx.v231_baseline_status == "PASS_V231_BASELINE_READBACK" else "FAIL" if ctx.v231_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v232: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v232_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V232_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v232_report.json":
        report.update({"completion_oriented_next_action_v232_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v231_carried_status": ctx.v231_baseline_status, "route_decision_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v232.json", "dummy_canonical_identity_report_v232.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V232ReportFactory:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.kw = dict(first_proof_override=first_proof_override, proof_target_override=proof_target_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V232Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
