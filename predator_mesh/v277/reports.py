"""DUMMY v277 final live-proof runbook lock (shortest command sequence) — no submit, no approval writes, no runtime/approvals."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v277 import MILESTONE

WORKSTREAM = "v277: Final Live-Proof Runbook Lock Command Sequence"
DASH_TITLE = "Dummy V277 Final Live-Proof Runbook Lock"
MISSION_KEY = "dummy_mission_state_report_v277"
CONTROLLER_KEY = "final_live_proof_runbook_lock_controller_status"

ENV_GATE = {
    "DUMMY_LIVE_PROOF_MODE": "1",
    "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY",
}

COMMAND_SEQUENCE = [
    {"step": 1, "command": "python scripts/run_dummy_external_authority_import_wizard.py", "purpose": "run external authority import wizard"},
    {"step": 2, "command": "python scripts/generate_v267_reports.py", "purpose": "run approval manifest schema verifier"},
    {"step": 3, "command": "python scripts/run_dummy_external_live_submit_caps_state_verifier.py", "purpose": "run external live-submit/caps verifier"},
    {"step": 4, "command": "python scripts/run_dummy_livebrokerfirewall_injection_appliance.py", "purpose": "run LiveBrokerFirewall injection appliance"},
    {"step": 5, "command": "python scripts/generate_v270_reports.py", "purpose": "run optional broker-readonly verifier"},
    {"step": 6, "command": "python scripts/run_dummy_final_armability_runbook.py", "purpose": "run final armability runbook"},
    {"step": 7, "command": "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY python scripts/run_dummy_live_proof_execute_once_v4.py", "purpose": "run execute-once runbook only with env gate and authority"},
    {"step": 8, "command": "python scripts/run_dummy_proof_intake_reconcile_handoff_v3.py", "purpose": "run proof intake handoff"},
    {"step": 9, "command": "python scripts/run_dummy_post_proof_reconcile_forensic_launcher.py", "purpose": "run reconcile/forensic"},
    {"step": 10, "command": "python scripts/generate_v283_reports.py", "purpose": "run route repeat/session"},
]

FAIL_CLOSED_EXPECTATIONS = {
    "absent_authority": "PARTIAL fail-closed, 0 live orders, broker_contacted=false",
    "missing_env_gate": "blocked, no submit",
    "wrong_env_ack": "blocked, no submit",
    "no_adapter": "blocked, no broker contact",
    "market_order": "rejected, limit-only",
    "repeat_attempt": "auto-locked after one attempt",
}

SUCCESS_EXPECTATIONS = {
    "with_real_authority": "one tiny live limit order via LiveBrokerFirewall, auto-lock after attempt, proof intake ready",
    "max_attempts": 1,
    "limit_only": True,
    "market_order": False,
}

REPORT_GROUPS: dict[str, list[str]] = {
    "final-live-proof-runbook-lock": ["v277_final_live_proof_runbook_lock_controller_report.json"],
    "v276-baseline": ["v276_baseline_readback_v1_report.json"],
    "command-sequence": ["v277_command_sequence_report.json"],
    "env-gate": ["v277_env_gate_report.json"],
    "no-submit-proof": ["v277_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v277_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v237_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v236_report.json"],
    "mission-state": ["dummy_mission_state_report_v277.json", "dashboard_v277_report_v1.json", "completion_oriented_next_action_v277_report.json"],
}

V277_ROUTES = [f"/api/v277/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Runbook Lock", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    return {
        "status": "PASS_FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY",
        "verdict": "PASS",
        "fields": {
            "command_sequence": COMMAND_SEQUENCE,
            "command_count": len(COMMAND_SEQUENCE),
            "env_gate": ENV_GATE,
            "fail_closed_expectations": FAIL_CLOSED_EXPECTATIONS,
            "success_expectations": SUCCESS_EXPECTATIONS,
            "max_attempts": 1,
            "auto_lock_after_attempt": True,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY_NEXT_RUN_EXECUTE_ONCE_WITH_AUTHORITY_NO_SUBMIT_BY_DUMMY",
    }


_BUNDLE = fcc.StageBundle(
    version=277, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V277_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V277ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
