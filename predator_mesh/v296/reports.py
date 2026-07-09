"""DUMMY v296 operator execution fork (authority absent or armable) — single fork decision; default locked; no submit, no broker contact, no approval writes."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v296 import MILESTONE

WORKSTREAM = "v296: Operator Execution Fork Authority Absent Or Armable"
DASH_TITLE = "Dummy V296 Operator Execution Fork"
MISSION_KEY = "dummy_mission_state_report_v296"
CONTROLLER_KEY = "operator_execution_fork_controller_status"

REPORT_GROUPS: dict[str, list[str]] = {
    "operator-execution-fork": ["v296_operator_execution_fork_controller_report.json"],
    "v295-baseline": ["v295_baseline_readback_v1_report.json"],
    "fork-state": ["v296_fork_state_report.json"],
    "no-submit-proof": ["v296_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v296_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v256_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v255_report.json"],
    "mission-state": ["dummy_mission_state_report_v296.json", "dashboard_v296_report_v1.json", "completion_oriented_next_action_v296_report.json"],
}

V296_ROUTES = [f"/api/v296/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Fork", CONTROLLER_KEY], ["State", "fork_state"], ["Next Action", "current_next_action"]]


def _resolve(authority: dict[str, Any] | None, already_locked: bool) -> tuple[str, str, str]:
    if already_locked:
        return "FORK_EXECUTION_ALREADY_LOCKED", "PARTIAL", "PARTIAL_OPERATOR_EXECUTION_FORK_EXECUTION_ALREADY_LOCKED"
    a = authority or {}
    if not (a.get("import_ok") and a.get("caps_ok_prereq", True) and a.get("authority_present")):
        return "FORK_LOCKED_AUTHORITY_ABSENT", "PARTIAL", "PARTIAL_OPERATOR_EXECUTION_FORK_LOCKED_AUTHORITY_ABSENT"
    if not a.get("caps_ok"):
        return "FORK_LOCKED_CONFIG_CAPS_ABSENT", "PARTIAL", "PARTIAL_OPERATOR_EXECUTION_FORK_LOCKED_CONFIG_CAPS_ABSENT"
    if not a.get("adapter_ok"):
        return "FORK_LOCKED_ADAPTER_ABSENT", "PARTIAL", "PARTIAL_OPERATOR_EXECUTION_FORK_LOCKED_ADAPTER_ABSENT"
    if not a.get("env_gate"):
        return "FORK_LOCKED_ENV_GATE_ABSENT", "PARTIAL", "PARTIAL_OPERATOR_EXECUTION_FORK_LOCKED_ENV_GATE_ABSENT"
    return "FORK_ARMABLE_NO_SUBMIT", "PASS", "PASS_OPERATOR_EXECUTION_FORK_ARMABLE_NO_SUBMIT"


def _controller(baseline_status: str, authority: dict[str, Any] | None = None, already_locked: bool = False, **kw: Any) -> dict[str, Any]:
    st = fcc.read_authority_state()
    state, verdict, status = _resolve(authority, already_locked)
    checks = {
        "external_authority_import_status": "READY" if st["import_ok"] else "PENDING",
        "live_submit_caps_verifier_status": "READY" if st["caps_ok"] else "PENDING",
        "firewall_adapter_status": "READY" if st["adapter_ok"] else "PENDING",
        "armability_runbook_status": "READY" if st["armable_ok"] else "PENDING",
        "no_surprises_precheck_status": "AWAIT_OPERATOR",
        "proof_lock_status": "CLEAR",
        "env_gate_present": bool((authority or {}).get("env_gate")),
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "fork_state": state,
            "fork_checks": checks,
            "order_submitted": False,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "OPERATOR_EXECUTION_FORK_" + state + "_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=296, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V296_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


def armable_authority() -> dict[str, Any]:
    """Fixture: fully armable external authority packet (tests only). No real submit downstream."""
    return {"import_ok": True, "authority_present": True, "caps_ok": True, "adapter_ok": True, "env_gate": True}


class V296ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
