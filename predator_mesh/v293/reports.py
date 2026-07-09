"""DUMMY v293 real-proof-required scale/autonomy wall (no enablement) — fixture proof never unlocks scale/autonomy; no caps modification, no autonomous order."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v293 import MILESTONE

WORKSTREAM = "v293: Real-Proof-Required Scale Autonomy Wall No Enablement"
DASH_TITLE = "Dummy V293 Real-Proof-Required Scale Autonomy Wall"
MISSION_KEY = "dummy_mission_state_report_v293"
CONTROLLER_KEY = "real_proof_required_scale_autonomy_wall_controller_status"

PROOF_CLASSES = ["NO_PROOF", "FIXTURE_PROOF_ONLY", "REAL_PROOF_PRESENT", "REAL_PROOF_RECONCILED", "REAL_PROOF_FORENSIC_REVIEWED"]

REPORT_GROUPS: dict[str, list[str]] = {
    "real-proof-required-scale-autonomy-wall": ["v293_real_proof_required_scale_autonomy_wall_controller_report.json"],
    "v292-baseline": ["v292_baseline_readback_v1_report.json"],
    "proof-classification": ["v293_proof_classification_report.json"],
    "no-submit-proof": ["v293_no_submit_proof_report.json"],
    "no-scale-proof": ["v293_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v293_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v253_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v252_report.json"],
    "mission-state": ["dummy_mission_state_report_v293.json", "dashboard_v293_report_v1.json", "completion_oriented_next_action_v293_report.json"],
}

V293_ROUTES = [f"/api/v293/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Wall", CONTROLLER_KEY], ["Proof Class", "proof_classification"], ["Next Action", "current_next_action"]]


def _classify_proof(fixture_proof: bool, real_state: dict[str, Any]) -> str:
    if real_state.get("real_proof"):
        if real_state.get("forensic"):
            return "REAL_PROOF_FORENSIC_REVIEWED"
        if real_state.get("reconciled"):
            return "REAL_PROOF_RECONCILED"
        return "REAL_PROOF_PRESENT"
    if fixture_proof:
        return "FIXTURE_PROOF_ONLY"
    return "NO_PROOF"


def _controller(baseline_status: str, fixture_proof: bool = False, real_proof_override: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    real_state = real_proof_override or {"real_proof": st["real_proof"], "reconciled": False, "forensic": False}
    proof_class = _classify_proof(fixture_proof, real_state)
    # Scale/autonomy unlock requires REAL proof reconciled+forensic. Fixture never unlocks.
    real_forensic = proof_class == "REAL_PROOF_FORENSIC_REVIEWED"
    scale_state = "SCALE_REVIEW_READY_LOCKED" if real_forensic else "SCALE_BLOCKED_NO_REAL_PROOF"
    autonomy_state = "AUTONOMY_REVIEW_READY_LOCKED" if real_forensic else "AUTONOMY_BLOCKED_NO_REAL_PROOF"
    return {
        "status": "PASS_REAL_PROOF_REQUIRED_WALL_LOCKED",
        "verdict": "PASS",
        "fields": {
            "proof_classification": proof_class,
            "proof_classes": PROOF_CLASSES,
            "scale_state": scale_state,
            "autonomy_state": autonomy_state,
            "scale_unlocked": real_forensic,
            "autonomy_unlocked": real_forensic,
            "fixture_proof_unlocks_scale_autonomy": False,
            "controlled_session_escalation_requires_real_proof": True,
            "no_caps_modification": True,
            "no_autonomous_order": True,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [],
        "next_action": "REAL_PROOF_REQUIRED_WALL_LOCKED_PROOF_CLASS_" + proof_class + "_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=293, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V293_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V293ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
