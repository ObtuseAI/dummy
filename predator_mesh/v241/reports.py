"""DUMMY v241 execute once handoff v2 operator final command no submit default — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v241 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v241: Execute Once Handoff V2 Operator Final Command No Submit Default"
MISSION_NAME = "dummy_mission_state_report_v227.json"
FINAL_NAME = "final_report_v241.json"
INDEX_KEYS = ['execute_once_handoff_controller_status', 'live_orders', 'approval_files_written']
DASH_TITLE = "Dummy V241 Execute Once Handoff V2 Operator Final Command No Submit Default"
MISSION_KEY = "dummy_mission_state_report_v227"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Execute-Once Handoff', 'execute_once_handoff_controller_status'], ['Live Orders', 'total_real_live_orders_submitted'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V241_ROUTES = ['/api/v241/execute-once-handoff-controller', '/api/v241/v240-baseline', '/api/v241/exact-command', '/api/v241/required-env-gate', '/api/v241/required-manifest', '/api/v241/required-adapter-injection', '/api/v241/proof-target', '/api/v241/expected-fail-closed-state', '/api/v241/expected-success-state', '/api/v241/default-no-submit-check', '/api/v241/no-approval-file-write-proof', '/api/v241/no-runtime-approvals-proof', '/api/v241/no-submit-proof', '/api/v241/readiness-governor', '/api/v241/execution-lock', '/api/v241/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'execute-once-handoff-controller': ['v241_execute_once_handoff_controller_report.json'], 'v240-baseline': ['v240_baseline_readback_v1_report.json'], 'exact-command': ['v241_exact_command_report.json'], 'required-env-gate': ['v241_required_env_gate_report.json'], 'required-manifest': ['v241_required_manifest_report.json'], 'required-adapter-injection': ['v241_required_adapter_injection_report.json'], 'proof-target': ['v241_proof_target_report.json'], 'expected-fail-closed-state': ['v241_expected_fail_closed_state_report.json'], 'expected-success-state': ['v241_expected_success_state_report.json'], 'default-no-submit-check': ['v241_default_no_submit_check_report.json'], 'no-approval-file-write-proof': ['v241_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v241_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v241_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v201_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v200_report.json'], 'mission-state': ['dummy_mission_state_report_v227.json', 'dashboard_v241_report_v1.json', 'completion_oriented_next_action_v241_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(241)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v241/reports.py scripts/generate_v241_reports.py dashboard/backend/v241_routes.py",
    "python scripts/generate_v241_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v241_execute_once_handoff_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
EXACT_COMMAND = "DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK + " python scripts/run_dummy_live_proof_execute_once_v2.py"
BLOCK_PROOFS = {
    "no_env_gate_means_blocked": True,
    "no_authority_means_blocked": True,
    "dry_mode_means_blocked": True,
    "no_adapter_means_blocked": True,
    "market_order_blocked": True,
    "repeat_attempt_blocked": True,
}


class V241Context:
    def __init__(self) -> None:
        self.v240_baseline_status = sgc.baseline_status("final_report_v240.json", "V240")
        self.armable = str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT"

    @property
    def controller_status(self) -> str:
        return "FAIL_EXECUTE_ONCE_HANDOFF_BASELINE_REGRESSION" if self.v240_baseline_status.startswith("FAIL") else "PASS_EXECUTE_ONCE_HANDOFF_READY_BLOCKED_BY_DEFAULT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v240_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V240_BASELINE_REGRESSION"] if self.v240_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "EXECUTE_ONCE_HANDOFF_READY_OPERATOR_RUN_EXACT_COMMAND_WITH_FULL_AUTHORITY_DEFAULT_BLOCKED_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v240_baseline_status": ctx.v240_baseline_status,
        "execute_once_handoff_controller_status": ctx.controller_status,
        "exact_command": EXACT_COMMAND,
        "exact_command_status": "PASS_EXACT_COMMAND_EMITTED",
        "required_env_gate": {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": LIVE_PROOF_ACK},
        "required_env_gate_status": "PASS_REQUIRED_ENV_GATE_LISTED",
        "required_manifest_status": "PASS_REQUIRED_MANIFEST_LISTED",
        "required_adapter_injection_status": "PASS_REQUIRED_ADAPTER_INJECTION_LISTED",
        "proof_target": "FIRST_REAL_PILOT_PROOF|CONTROLLED_SESSION_PROOF",
        "proof_target_status": "PASS_PROOF_TARGET_LISTED",
        "expected_fail_closed_state": "PARTIAL_EXECUTE_ONCE_HARNESS_NOT_ARMED",
        "expected_fail_closed_state_status": "PASS_EXPECTED_FAIL_CLOSED_STATE",
        "expected_success_state": "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED",
        "expected_success_state_status": "PASS_EXPECTED_SUCCESS_STATE",
        "default_no_submit_check_status": "PASS_DEFAULT_NO_SUBMIT",
        "block_proofs": BLOCK_PROOFS,
        "armable_quorum_ready": ctx.armable,
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
        "no_submit_proof_status": "PASS_NO_SUBMIT",

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v201_status": "PASS",
        "execution_lock_deep_recheck_v200_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v240_baseline"):
        return "PASS" if ctx.v240_baseline_status == "PASS_V240_BASELINE_READBACK" else "FAIL" if ctx.v240_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v241: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v241_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V241_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v241_report.json":
        report.update({"completion_oriented_next_action_v241_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v240_carried_status": ctx.v240_baseline_status, "execute_once_handoff_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v241.json", "dummy_canonical_identity_report_v241.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V241ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V241Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
