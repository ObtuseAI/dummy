"""DUMMY v287 final run appliance launcher (dry default) — single dry pipeline; no submit, no broker contact, no config/caps mutation."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v287 import MILESTONE

WORKSTREAM = "v287: Final Run Appliance Launcher Dry Default"
DASH_TITLE = "Dummy V287 Final Run Appliance Launcher"
MISSION_KEY = "dummy_mission_state_report_v287"
CONTROLLER_KEY = "final_run_appliance_launcher_controller_status"

DRY_PIPELINE = [
    {"step": 1, "stage": "V285 baseline"},
    {"step": 2, "stage": "V286 authority seal"},
    {"step": 3, "stage": "final armability runbook"},
    {"step": 4, "stage": "pre-execution freeze check"},
    {"step": 5, "stage": "execute-once default blocked check"},
    {"step": 6, "stage": "attempt monitor"},
    {"step": 7, "stage": "route command center"},
    {"step": 8, "stage": "completion lift"},
]

REPORT_GROUPS: dict[str, list[str]] = {
    "final-run-appliance-launcher": ["v287_final_run_appliance_launcher_controller_report.json"],
    "v286-baseline": ["v286_baseline_readback_v1_report.json"],
    "dry-pipeline": ["v287_dry_pipeline_report.json"],
    "no-submit-proof": ["v287_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v287_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v247_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v246_report.json"],
    "mission-state": ["dummy_mission_state_report_v287.json", "dashboard_v287_report_v1.json", "completion_oriented_next_action_v287_report.json"],
}

V287_ROUTES = [f"/api/v287/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Appliance", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    return {
        "status": "PASS_FINAL_RUN_APPLIANCE_DRY_COMPLETE",
        "verdict": "PASS",
        "fields": {
            "dry_pipeline": DRY_PIPELINE,
            "dry_pipeline_step_count": len(DRY_PIPELINE),
            "livebrokerfirewall_submit_called": False,
            "broker_payload_created_by_default": False,
            "config_caps_mutated": False,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "FINAL_RUN_APPLIANCE_DRY_COMPLETE_NEXT_RUN_NO_SURPRISES_PRECHECK_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=287, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V287_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V287ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
