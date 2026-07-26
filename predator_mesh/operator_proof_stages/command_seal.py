"""DUMMY v297 execute-once command seal (final env/authority/idempotency lock) — default blocked; no submit, no broker contact, no mutation."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh import staged_gate_common as sgc
from predator_mesh.authority_contracts import CAPS_HASH, LIVE_SUBMIT_HASH

MILESTONE = "DUMMY_V297_EXECUTE_ONCE_COMMAND_SEAL_FINAL_ENV_AUTHORITY_AND_IDEMPOTENCY_LOCK_V1"
WORKSTREAM = "v297: Execute-Once Command Seal Final Env Authority And Idempotency Lock"
DASH_TITLE = "Dummy V297 Execute-Once Command Seal"
MISSION_KEY = "dummy_mission_state_report_v297"
CONTROLLER_KEY = "execute_once_command_seal_controller_status"

EXACT_COMMAND = "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY python scripts/run_dummy_execute_once_final_proof_v7.py"
ENV_GATE = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}

REPORT_GROUPS: dict[str, list[str]] = {
    "execute-once-command-seal": ["v297_execute_once_command_seal_controller_report.json"],
    "v296-baseline": ["v296_baseline_readback_v1_report.json"],
    "seal-manifest": ["v297_seal_manifest_report.json"],
    "no-submit-proof": ["v297_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v297_no_broker_contact_proof_report.json"],
    "no-mutation-proof": ["v297_no_mutation_proof_report.json"],
    "readiness-governor": ["readiness_governor_v257_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v256_report.json"],
    "mission-state": ["dummy_mission_state_report_v297.json", "dashboard_v297_report_v1.json", "completion_oriented_next_action_v297_report.json"],
}

V297_ROUTES = [f"/api/v297/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Seal", CONTROLLER_KEY], ["State", "seal_state"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, seal: dict[str, Any] | None = None, already_used: bool = False, **kw: Any) -> dict[str, Any]:
    if already_used:
        state, verdict, status = "COMMAND_SEAL_ALREADY_USED_LOCKED", "PARTIAL", "PARTIAL_COMMAND_SEAL_ALREADY_USED_LOCKED"
    elif not seal or not seal.get("authority_ready"):
        state, verdict, status = "COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT", "PARTIAL", "PARTIAL_COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT"
    else:
        state, verdict, status = "COMMAND_SEAL_READY_NO_SUBMIT", "PASS", "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"
    manifest = {
        "exact_command": EXACT_COMMAND,
        "env_gate": ENV_GATE,
        "proof_target": (seal or {}).get("proof_target", "FIRST_REAL_PILOT_PROOF"),
        "proof_lock_status": "CLEAR",
        "idempotency_key": (seal or {}).get("idempotency_key", "PENDING_OPERATOR"),
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
        "adapter_descriptor_hash": sgc.approval_hash((seal or {}).get("adapter_descriptor", {})) if seal else "",
        "authority_manifest_hash": sgc.approval_hash((seal or {}).get("manifest", {})) if seal else "",
        "expected_success_artifact": "final_report_v298.json (PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED)",
        "expected_blocked_artifact": "final_report_v298.json (PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED)",
    }
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "seal_state": state,
            "seal_manifest": manifest,
            "max_attempts": 1,
            "auto_lock_after_attempt": True,
            "raw_phrase_serialized": False,
            "configs_mutated": False,
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            "no_mutation_proof_status": "PASS_NO_MUTATION",
        },
        "blockers": [] if verdict == "PASS" else [state],
        "next_action": "EXECUTE_ONCE_COMMAND_SEAL_" + state + "_NO_SUBMIT_NO_BROKER_CONTACT",
    }


_BUNDLE = fcc.StageBundle(
    version=297, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V297_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/operator_proof_stages/command_seal.py predator_mesh/operator_proof_workflows.py scripts/run_dummy_execute_once_command_seal.py",
    "python scripts/run_dummy_execute_once_command_seal.py",
    "python -m pytest tests/test_v295_to_v304_governance.py tests/test_predator_mesh_coupling_surface.py -q",
]


def ready_seal() -> dict[str, Any]:
    """Fixture: authority-ready seal packet (tests only)."""
    return {"authority_ready": True, "proof_target": "FIRST_REAL_PILOT_PROOF", "idempotency_key": "K1",
            "adapter_descriptor": {"firewall": True}, "manifest": {"version": "v3"}}


class CommandSealReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
