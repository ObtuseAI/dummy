"""DUMMY v301 post-proof route autopilot (repeat/session/repair/stop) — default blocked by no real proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
MILESTONE = "DUMMY_V301_POST_PROOF_ROUTE_AUTOPILOT_REPEAT_SESSION_OR_REPAIR_V1"

WORKSTREAM = "v301: Post-Proof Route Autopilot Repeat Session Or Repair"
DASH_TITLE = "Dummy V301 Post-Proof Route Autopilot"
MISSION_KEY = "dummy_mission_state_report_v301"
CONTROLLER_KEY = "post_proof_route_autopilot_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "post-proof-route-autopilot": ["v301_post_proof_route_autopilot_controller_report.json"],
    "v300-baseline": ["v300_baseline_readback_v1_report.json"],
    "route-state": ["v301_route_state_report.json"],
    "no-submit-proof": ["v301_no_submit_proof_report.json"],
    "no-scale-proof": ["v301_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v301_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v261_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v260_report.json"],
    "mission-state": ["dummy_mission_state_report_v301.json", "dashboard_v301_report_v1.json", "completion_oriented_next_action_v301_report.json"],
}

V301_ROUTES = [f"/api/v301/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Route", CONTROLLER_KEY], ["State", "route_state"], ["Next Action", "current_next_action"]]


def _resolve(real_proof: bool, reconcile: bool, forensic: bool, route: str, repair: bool, stop: bool) -> tuple[str, str, str]:
    if repair:
        return "ROUTE_REPAIR_REQUIRED", "PARTIAL", "PARTIAL_ROUTE_REPAIR_REQUIRED"
    if not real_proof:
        return "ROUTE_BLOCKED_NO_REAL_PROOF", "PARTIAL", "PARTIAL_ROUTE_BLOCKED_NO_REAL_PROOF"
    if not reconcile:
        return "ROUTE_BLOCKED_NO_RECONCILE", "PARTIAL", "PARTIAL_ROUTE_BLOCKED_NO_RECONCILE"
    if not forensic:
        return "ROUTE_BLOCKED_NO_FORENSIC", "PARTIAL", "PARTIAL_ROUTE_BLOCKED_NO_FORENSIC"
    if stop:
        return "ROUTE_STOP_LOCKED", "PASS", "PASS_POST_PROOF_ROUTE_AUTOPILOT_READY_LOCKED"
    if route == "session":
        return "ROUTE_CONTROLLED_SESSION_READY_LOCKED", "PASS", "PASS_POST_PROOF_ROUTE_AUTOPILOT_READY_LOCKED"
    return "ROUTE_REPEAT_PILOT_READY_LOCKED", "PASS", "PASS_POST_PROOF_ROUTE_AUTOPILOT_READY_LOCKED"


def _controller(baseline_status: str, real_proof: bool = False, reconcile: bool = False, forensic: bool = False,
                route: str = "repeat", repair_required: bool = False, stop: bool = False, **kw: Any) -> dict[str, Any]:
    state, verdict, status = _resolve(real_proof, reconcile, forensic, route, repair_required, stop)
    evaluate = {
        "proof_state": "PRESENT" if real_proof else "ABSENT",
        "reconcile_state": "PRESENT" if reconcile else "ABSENT",
        "forensic_state": "PRESENT" if forensic else "ABSENT",
        "risk_behavior": "OK",
        "abstention_behavior": "OK",
        "slippage_bucket": "n/a",
        "latency_bucket": "n/a",
        "fee_bucket": "n/a",
        "live_submit_caps_unchanged": True,
        "adapter_status": "AWAIT_OPERATOR",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "route_state": state,
            "route_evaluation": evaluate,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "POST_PROOF_ROUTE_AUTOPILOT_" + state + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=301, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V301_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/operator_proof_stages/post_proof.py predator_mesh/operator_proof_workflows.py scripts/run_dummy_post_proof_route_autopilot.py",
    "python scripts/run_dummy_post_proof_route_autopilot.py",
    "python -m pytest tests/test_v295_to_v304_governance.py -q",
]


class PostProofRouteReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
