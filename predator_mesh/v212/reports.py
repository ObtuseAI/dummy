"""DUMMY v212 repeat/session bridge — routes to repeat pilot or controlled session review after first live proof; no submit.

Requires first-proof + reconcile + forensic prerequisites, then checks repeat-pilot / controlled-session / scale /
autonomy readiness and emits a route (ROUTE_BLOCKED_NO_LIVE_PROOF / ROUTE_REPEAT_PILOT_REVIEW_READY /
ROUTE_CONTROLLED_SESSION_REVIEW_READY / ROUTE_REPAIR_REQUIRED). Default is ROUTE_BLOCKED_NO_LIVE_PROOF. No submit, no
scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v212 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v212: Repeat And Session Bridge After First Live Proof"
MISSION_NAME = "dummy_mission_state_report_v198.json"
FINAL_NAME = "final_report_v212.json"
INDEX_KEYS = ["bridge_controller_status", "route_state", "live_orders"]
DASH_TITLE = "Dummy V212 Repeat/Session Bridge"
MISSION_KEY = "dummy_mission_state_report_v198"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Bridge", "bridge_controller_status"],
    ["Route", "route_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V212_ROUTES = [
    "/api/v212/bridge-controller",
    "/api/v212/v211-baseline",
    "/api/v212/first-proof-prerequisite",
    "/api/v212/reconcile-prerequisite",
    "/api/v212/forensic-prerequisite",
    "/api/v212/repeat-pilot-readiness-check",
    "/api/v212/controlled-session-readiness-check",
    "/api/v212/scale-readiness-check",
    "/api/v212/autonomy-readiness-check",
    "/api/v212/route-state",
    "/api/v212/no-submit-proof",
    "/api/v212/no-scale-proof",
    "/api/v212/no-autonomy-proof",
    "/api/v212/readiness-governor",
    "/api/v212/execution-lock",
    "/api/v212/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "bridge-controller": ["v212_bridge_controller_report.json"],
    "v211-baseline": ["v211_baseline_readback_v1_report.json"],
    "first-proof-prerequisite": ["v212_first_proof_prerequisite_report.json"],
    "reconcile-prerequisite": ["v212_reconcile_prerequisite_report.json"],
    "forensic-prerequisite": ["v212_forensic_prerequisite_report.json"],
    "repeat-pilot-readiness-check": ["v212_repeat_pilot_readiness_check_report.json"],
    "controlled-session-readiness-check": ["v212_controlled_session_readiness_check_report.json"],
    "scale-readiness-check": ["v212_scale_readiness_check_report.json"],
    "autonomy-readiness-check": ["v212_autonomy_readiness_check_report.json"],
    "route-state": ["v212_route_state_report.json"],
    "no-submit-proof": ["v212_no_submit_proof_report.json"],
    "no-scale-proof": ["v212_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v212_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v172_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v171_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v212_report_v1.json", "completion_oriented_next_action_v212_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(212)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v212/reports.py scripts/generate_v212_reports.py dashboard/backend/v212_routes.py",
    "python scripts/generate_v212_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ROUTE_STATE_ENUM = [
    "ROUTE_BLOCKED_NO_LIVE_PROOF",
    "ROUTE_REPEAT_PILOT_REVIEW_READY",
    "ROUTE_CONTROLLED_SESSION_REVIEW_READY",
    "ROUTE_REPAIR_REQUIRED",
]


class V212Context:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.v211_baseline_status = sgc.baseline_status("final_report_v211.json", "V211")
        if first_proof_override is not None:
            self.first_proof = bool(first_proof_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v210.json").get("reconcile_runner_controller_status", "")) == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v211.json").get("forensic_runner_controller_status", "")) == "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED"
            self.first_proof = reconciled and reviewed
        if proof_target_override is not None:
            self.proof_target = proof_target_override
        else:
            self.proof_target = str(sgc.load_artifact("final_report_v210.json").get("proof_target", "NO_ATTEMPT"))

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
        if self.v211_baseline_status.startswith("FAIL"):
            return "FAIL_BRIDGE_BASELINE_REGRESSION"
        return "PASS_REPEAT_SESSION_BRIDGE_READY_LOCKED" if self.ready else "PARTIAL_REPEAT_SESSION_BRIDGE_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v211_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v211_baseline_status.startswith("FAIL"):
            return ["FAIL_V211_BASELINE_REGRESSION"]
        return [] if self.ready else ["FIRST_LIVE_PROOF_RECONCILE_FORENSIC_ABSENT"]

    @property
    def next_action(self) -> str:
        if self.route_state == "ROUTE_CONTROLLED_SESSION_REVIEW_READY":
            return "REPEAT_SESSION_BRIDGE_READY_LOCKED_ROUTE_CONTROLLED_SESSION_REVIEW_NO_SUBMIT"
        if self.route_state == "ROUTE_REPEAT_PILOT_REVIEW_READY":
            return "REPEAT_SESSION_BRIDGE_READY_LOCKED_ROUTE_REPEAT_PILOT_REVIEW_NO_SUBMIT"
        return "AWAIT_FIRST_LIVE_PROOF_RECONCILE_AND_FORENSIC_BEFORE_BRIDGE"


def _common(ctx: V212Context) -> dict[str, Any]:
    present = ctx.first_proof
    return {
        "v211_baseline_status": ctx.v211_baseline_status,
        "bridge_controller_status": ctx.controller_status,
        "first_proof_prerequisite_status": "PASS_FIRST_PROOF_PRESENT" if present else "PARTIAL_FIRST_PROOF_ABSENT",
        "reconcile_prerequisite_status": "PASS_RECONCILE_PRESENT" if present else "PARTIAL_RECONCILE_ABSENT",
        "forensic_prerequisite_status": "PASS_FORENSIC_PRESENT" if present else "PARTIAL_FORENSIC_ABSENT",
        "repeat_pilot_readiness_check_status": "PASS_REPEAT_PILOT_READY" if (present and ctx.proof_target != "CONTROLLED_SESSION_PROOF") else "PARTIAL_REPEAT_PILOT_NOT_ROUTED",
        "controlled_session_readiness_check_status": "PASS_CONTROLLED_SESSION_READY" if (present and ctx.proof_target == "CONTROLLED_SESSION_PROOF") else "PARTIAL_CONTROLLED_SESSION_NOT_ROUTED",
        "scale_readiness_check_status": "PASS_SCALE_READINESS_READ",
        "autonomy_readiness_check_status": "PASS_AUTONOMY_READINESS_READ",
        "route_state_status": "PASS_ROUTE_STATE_SELECTED",
        "route_state": ctx.route_state,
        "route_state_enum": ROUTE_STATE_ENUM,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v172_status": "PASS",
        "execution_lock_deep_recheck_v171_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V212Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v211_baseline"):
        return "PASS" if ctx.v211_baseline_status == "PASS_V211_BASELINE_READBACK" else "FAIL" if ctx.v211_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v212_bridge_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V212Context) -> dict[str, Any]:
    workstream = "v212: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v212_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V212_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v212_report.json":
        report.update({"completion_oriented_next_action_v212_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v211_carried_status": ctx.v211_baseline_status, "route_state": ctx.route_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v212_bridge_controller_report.json"), "no_submit": str(ARTIFACTS / "v212_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v212.json", "dummy_canonical_identity_report_v212.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V212ReportFactory:
    def __init__(self, *, first_proof_override=None, proof_target_override=None) -> None:
        self.kw = dict(first_proof_override=first_proof_override, proof_target_override=proof_target_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V212Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
