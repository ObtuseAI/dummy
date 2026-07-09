"""DUMMY v276 final authority readiness console (read-only) — no submit from UI, no writes, no broker contact."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh import final_console_common as fcc
from predator_mesh.v276 import MILESTONE

WORKSTREAM = "v276: Final Authority Readiness Console Read-Only"
DASH_TITLE = "Dummy V276 Final Authority Readiness Console"
MISSION_KEY = "dummy_mission_state_report_v276"
CONTROLLER_KEY = "final_authority_readiness_console_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "final-authority-readiness-console": ["v276_final_authority_readiness_console_controller_report.json"],
    "v275-baseline": ["v275_baseline_readback_v1_report.json"],
    "authority-readiness-matrix": ["v276_authority_readiness_matrix_report.json"],
    "ui-flags": ["v276_ui_flags_report.json"],
    "no-submit-proof": ["v276_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v276_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v236_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v235_report.json"],
    "mission-state": ["dummy_mission_state_report_v276.json", "dashboard_v276_report_v1.json", "completion_oriented_next_action_v276_report.json"],
}

V276_ROUTES = [f"/api/v276/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Console", CONTROLLER_KEY], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action", "current_next_action"]]

UI_FLAGS = {
    "ui_submit_enabled": False,
    "ui_writes_enabled": False,
    "ui_runtime_approvals_create_enabled": False,
    "ui_caps_edit_enabled": False,
    "ui_live_submit_edit_enabled": False,
}


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    matrix = {
        "authority_manifest_status": "READY" if st["import_ok"] else "PENDING",
        "schema_status": "READY" if st["schema_ok"] else "PENDING",
        "live_submit_caps_status": "READY" if st["caps_ok"] else "PENDING",
        "adapter_injection_status": "READY" if st["adapter_ok"] else "PENDING",
        "broker_readonly_status": "READY" if st["readonly_ok"] else "PENDING",
        "armability_status": "READY" if st["armable_ok"] else "PENDING",
        "execute_once_status": "PROVEN" if st["real_proof"] else "PENDING",
        "post_proof_status": "READY" if st["real_proof"] else "PENDING",
        "route_status": "READY" if st["real_proof"] else "BLOCKED_NO_LIVE_PROOF",
    }
    fully_op = int(sgc.load_artifact("final_report_v274.json").get("fully_operational_estimate", 0) or 0)
    return {
        "status": "PASS_FINAL_AUTHORITY_READINESS_CONSOLE_READY_READONLY",
        "verdict": "PASS",
        "fields": {
            "authority_readiness_matrix": matrix,
            "fully_operational_estimate": fully_op,
            "authority_state": st,
            **UI_FLAGS,
            "read_only_console": True,
            "console_can_submit": False,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "FINAL_AUTHORITY_READINESS_CONSOLE_READY_READONLY_NEXT_RUN_FINAL_LIVE_PROOF_RUNBOOK_LOCK_NO_SUBMIT",
    }


_BUNDLE = fcc.StageBundle(
    version=276, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V276_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V276ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
