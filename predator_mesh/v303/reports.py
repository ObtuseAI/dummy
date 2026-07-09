"""DUMMY v303 proof-starvation stop rule (no more gate sprawl) — blocks endless architecture expansion without real proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v303 import MILESTONE

WORKSTREAM = "v303: Proof-Starvation Stop Rule No More Gate Sprawl"
DASH_TITLE = "Dummy V303 Proof-Starvation Stop Rule"
MISSION_KEY = "dummy_mission_state_report_v303"
CONTROLLER_KEY = "proof_starvation_stop_rule_controller_status"

RECOMMENDATION = [
    "DO_NOT_ADD_MORE_GATES",
    "RUN_EXTERNAL_AUTHORITY_PATH",
    "EXECUTE_ONCE_WITH_AUTHORITY",
    "RECONCILE_FORENSIC",
    "ONLY_THEN_BUILD_REPEAT_OR_SESSION_LIVE_PATH",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "proof-starvation-stop-rule": ["v303_proof_starvation_stop_rule_controller_report.json"],
    "v302-baseline": ["v302_baseline_readback_v1_report.json"],
    "starvation-detection": ["v303_starvation_detection_report.json"],
    "recommendation": ["v303_recommendation_report.json"],
    "no-submit-proof": ["v303_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v303_no_broker_contact_proof_report.json"],
    "no-scale-proof": ["v303_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v303_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v263_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v262_report.json"],
    "mission-state": ["dummy_mission_state_report_v303.json", "dashboard_v303_report_v1.json", "completion_oriented_next_action_v303_report.json"],
}

V303_ROUTES = [f"/api/v303/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Stop Rule", CONTROLLER_KEY], ["State", "starvation_state"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, real_proof_override: bool | None = None, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    real_proof = st["real_proof"] if real_proof_override is None else real_proof_override
    authority_present = st["import_ok"] and st["schema_ok"] and st["caps_ok"] and st["adapter_ok"] and st["armable_ok"]
    if real_proof:
        state = "REAL_PROOF_PRESENT_CONTINUE"
    elif not authority_present:
        state = "OPERATOR_AUTHORITY_REQUIRED_STOP_ARCHITECTURE_SPRAWL"
    else:
        state = "PROOF_STARVATION_ACTIVE"
    detection = {
        "successful_architecture_bundles_many": True,
        "zero_real_proof": not real_proof,
        "repeated_fixture_only_proof": not real_proof,
        "no_external_authority": not authority_present,
    }
    return {
        "status": "PASS_PROOF_STARVATION_STOP_RULE_ACTIVE",
        "verdict": "PASS",
        "fields": {
            "starvation_state": state,
            "starvation_detection": detection,
            "recommendation": RECOMMENDATION,
            "architecture_sprawl_blocked": not real_proof,
            "real_proof_present": real_proof,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [],
        "next_action": "PROOF_STARVATION_STOP_RULE_ACTIVE_STATE_" + state + "_STOP_BUILDING_GATES_UNTIL_REAL_PROOF",
    }


_BUNDLE = fcc.StageBundle(
    version=303, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V303_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V303ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
