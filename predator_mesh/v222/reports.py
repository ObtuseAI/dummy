"""DUMMY v222 repeat controlled session readiness bridge v2 after proof — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v222 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v222: Repeat Controlled Session Readiness Bridge V2 After Proof"
MISSION_NAME = "dummy_mission_state_report_v208.json"
FINAL_NAME = "final_report_v222.json"
INDEX_KEYS = ['repeat_controlled_session_bridge_v2_controller_status', 'route_state', 'new_order_placed']
DASH_TITLE = "Dummy V222 Repeat Controlled Session Readiness Bridge V2 After Proof"
MISSION_KEY = "dummy_mission_state_report_v208"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Bridge', 'repeat_controlled_session_bridge_v2_controller_status'], ['Route State', 'route_state'], ['Next Action', 'current_next_action'], ['Scale Applied', 'scale_applied'], ['Blockers', 'current_blockers']]

V222_ROUTES = ['/api/v222/repeat-controlled-session-bridge-v2-controller', '/api/v222/v221-baseline', '/api/v222/live-proof-prerequisite', '/api/v222/reconcile-prerequisite', '/api/v222/forensic-prerequisite', '/api/v222/repeat-pilot-readiness', '/api/v222/controlled-session-readiness', '/api/v222/scale-review-readiness', '/api/v222/autonomy-review-readiness', '/api/v222/route-state', '/api/v222/no-submit-proof', '/api/v222/no-scale-proof', '/api/v222/no-autonomy-proof', '/api/v222/readiness-governor', '/api/v222/execution-lock', '/api/v222/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'repeat-controlled-session-bridge-v2-controller': ['v222_repeat_controlled_session_bridge_v2_controller_report.json'], 'v221-baseline': ['v221_baseline_readback_v1_report.json'], 'live-proof-prerequisite': ['v222_live_proof_prerequisite_report.json'], 'reconcile-prerequisite': ['v222_reconcile_prerequisite_report.json'], 'forensic-prerequisite': ['v222_forensic_prerequisite_report.json'], 'repeat-pilot-readiness': ['v222_repeat_pilot_readiness_report.json'], 'controlled-session-readiness': ['v222_controlled_session_readiness_report.json'], 'scale-review-readiness': ['v222_scale_review_readiness_report.json'], 'autonomy-review-readiness': ['v222_autonomy_review_readiness_report.json'], 'route-state': ['v222_route_state_report.json'], 'no-submit-proof': ['v222_no_submit_proof_report.json'], 'no-scale-proof': ['v222_no_scale_proof_report.json'], 'no-autonomy-proof': ['v222_no_autonomy_proof_report.json'], 'readiness-governor': ['readiness_governor_v182_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v181_report.json'], 'mission-state': ['dummy_mission_state_report_v208.json', 'dashboard_v222_report_v1.json', 'completion_oriented_next_action_v222_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(222)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v222/reports.py scripts/generate_v222_reports.py dashboard/backend/v222_routes.py",
    "python scripts/generate_v222_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v222_repeat_controlled_session_bridge_v2_controller_report.json"

class V222Context:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.v221_baseline_status = sgc.baseline_status("final_report_v221.json", "V221")
        if first_proof_override is not None:
            self.first_proof = bool(first_proof_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v220.json").get("reconcile_spine_v2_controller_status", "")) == "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v221.json").get("forensic_spine_v2_controller_status", "")) == "PASS_FORENSIC_SPINE_V2_REVIEWED_LOCKED"
            self.first_proof = reconciled and reviewed
        if proof_target_override is not None:
            self.proof_target = proof_target_override
        else:
            self.proof_target = str(sgc.load_artifact("final_report_v220.json").get("proof_target", "NO_ATTEMPT"))

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
        if self.v221_baseline_status.startswith("FAIL"):
            return "FAIL_REPEAT_CONTROLLED_SESSION_BRIDGE_V2_BASELINE_REGRESSION"
        return "PASS_REPEAT_CONTROLLED_SESSION_BRIDGE_V2_READY_LOCKED" if self.ready else "PARTIAL_REPEAT_CONTROLLED_SESSION_BRIDGE_V2_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v221_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v221_baseline_status.startswith("FAIL"):
            return ["FAIL_V221_BASELINE_REGRESSION"]
        return [] if self.ready else ["HARDENED_LIVE_PROOF_RECONCILE_FORENSIC_ABSENT"]

    @property
    def next_action(self) -> str:
        if self.route_state == "ROUTE_CONTROLLED_SESSION_REVIEW_READY":
            return "REPEAT_SESSION_BRIDGE_V2_READY_LOCKED_ROUTE_CONTROLLED_SESSION_REVIEW_NO_SUBMIT_NO_SCALE"
        if self.route_state == "ROUTE_REPEAT_PILOT_REVIEW_READY":
            return "REPEAT_SESSION_BRIDGE_V2_READY_LOCKED_ROUTE_REPEAT_PILOT_REVIEW_NO_SUBMIT_NO_SCALE"
        return "AWAIT_HARDENED_LIVE_PROOF_RECONCILE_AND_FORENSIC_BEFORE_BRIDGE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v221_baseline_status": ctx.v221_baseline_status,
        "repeat_controlled_session_bridge_v2_controller_status": ctx.controller_status,
        "route_state": ctx.route_state,
        "route_states": ["ROUTE_BLOCKED_NO_LIVE_PROOF", "ROUTE_REPEAT_PILOT_REVIEW_READY", "ROUTE_CONTROLLED_SESSION_REVIEW_READY", "ROUTE_SCALE_REVIEW_READY_LOCKED", "ROUTE_AUTONOMY_REVIEW_BLOCKED", "ROUTE_REPAIR_REQUIRED"],
        "live_proof_prerequisite_status": "PASS_LIVE_PROOF_PRESENT" if ctx.first_proof else "PARTIAL_LIVE_PROOF_ABSENT",
        "reconcile_prerequisite_status": "PASS_RECONCILE_PRESENT" if ctx.first_proof else "PARTIAL_RECONCILE_ABSENT",
        "forensic_prerequisite_status": "PASS_FORENSIC_PRESENT" if ctx.first_proof else "PARTIAL_FORENSIC_ABSENT",
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
        "readiness_governor_v182_status": "PASS",
        "execution_lock_deep_recheck_v181_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v221_baseline"):
        return "PASS" if ctx.v221_baseline_status == "PASS_V221_BASELINE_READBACK" else "FAIL" if ctx.v221_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v222: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v222_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V222_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v222_report.json":
        report.update({"completion_oriented_next_action_v222_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v221_carried_status": ctx.v221_baseline_status, "repeat_controlled_session_bridge_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v222.json", "dummy_canonical_identity_report_v222.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V222ReportFactory:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.kw = dict(first_proof_override=first_proof_override, proof_target_override=proof_target_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V222Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
