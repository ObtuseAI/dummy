"""DUMMY v288 live-proof no-surprises precheck (no submit) — default blocked; all-green-or-exact-blocker; no broker contact."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v288 import MILESTONE

WORKSTREAM = "v288: Live-Proof No-Surprises Precheck No Submit"
DASH_TITLE = "Dummy V288 Live-Proof No-Surprises Precheck"
MISSION_KEY = "dummy_mission_state_report_v288"
CONTROLLER_KEY = "live_proof_no_surprises_precheck_controller_status"

CHECKS = ["authority_seal", "live_submit_caps_immutable", "firewall_adapter", "broker_readonly_optional",
          "final_armability_runbook", "pre_execution_freeze", "env_gate", "idempotency", "proof_lock_clear",
          "candidate_risk_abstention", "no_market_order"]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-proof-no-surprises-precheck": ["v288_live_proof_no_surprises_precheck_controller_report.json"],
    "v287-baseline": ["v287_baseline_readback_v1_report.json"],
    "precheck-matrix": ["v288_precheck_matrix_report.json"],
    "no-submit-proof": ["v288_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v288_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v248_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v247_report.json"],
    "mission-state": ["dummy_mission_state_report_v288.json", "dashboard_v288_report_v1.json", "completion_oriented_next_action_v288_report.json"],
}

V288_ROUTES = [f"/api/v288/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Precheck", CONTROLLER_KEY], ["State", "precheck_state"], ["Next Action", "current_next_action"]]


def _resolve(seal: bool, config_caps: bool, adapter: bool, env_gate: bool, freeze: bool) -> tuple[str, str, str]:
    if not seal:
        return "PRECHECK_BLOCKED_AUTHORITY", "PARTIAL", "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_AUTHORITY"
    if not config_caps:
        return "PRECHECK_BLOCKED_CONFIG_CAPS", "PARTIAL", "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_CONFIG_CAPS"
    if not adapter:
        return "PRECHECK_BLOCKED_ADAPTER", "PARTIAL", "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_ADAPTER"
    if not env_gate:
        return "PRECHECK_BLOCKED_ENV_GATE", "PARTIAL", "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_ENV_GATE"
    if not freeze:
        return "PRECHECK_BLOCKED_FREEZE", "PARTIAL", "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_FREEZE"
    return "PRECHECK_READY_NO_SUBMIT", "PASS", "PASS_NO_SURPRISES_PRECHECK_READY_NO_SUBMIT"


def _controller(baseline_status: str, seal: bool = False, config_caps: bool = False, adapter: bool = False,
                env_gate: bool = False, freeze: bool = False, **kw: Any) -> dict[str, Any]:
    state, verdict, status = _resolve(seal, config_caps, adapter, env_gate, freeze)
    matrix = {
        "authority_seal": "GREEN" if seal else "BLOCKED",
        "live_submit_caps_immutable": "GREEN" if config_caps else "BLOCKED",
        "firewall_adapter": "GREEN" if adapter else "BLOCKED",
        "broker_readonly_optional": "GREEN",
        "final_armability_runbook": "GREEN" if (seal and config_caps and adapter) else "BLOCKED",
        "pre_execution_freeze": "GREEN" if freeze else "BLOCKED",
        "env_gate": "GREEN" if env_gate else "BLOCKED",
        "idempotency": "GREEN",
        "proof_lock_clear": "GREEN",
        "candidate_risk_abstention": "GREEN",
        "no_market_order": "GREEN",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "precheck_state": state,
            "precheck_matrix": matrix,
            "precheck_checks": CHECKS,
            "all_green": verdict == "PASS",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "NO_SURPRISES_PRECHECK_" + state + "_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=288, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V288_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V288ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
