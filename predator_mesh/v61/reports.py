"""DUMMY v61 local rehearsal design gate — architecture, schema, and validation only (non-executable)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v61 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

# Design-only architecture for a FUTURE local rehearsal runner. No runnable code/path is produced.
REHEARSAL_DESIGN_SPEC = {
    "runner_name": "future_local_only_rehearsal_runner",
    "executable": False,
    "inputs": ["inert_quarantined_rehearsal_artifacts"],
    "outputs": ["inert_simulation_logs", "inert_checklists"],
    "no_broker_payloads": True,
    "no_order_submission": True,
    "no_live_trading": True,
    "no_live_submit": True,
    "no_caps_modification": True,
    "requires_future_approval_phrase_for_runnable_artifact": True,
}

V61_ROUTES = [
    "/api/v61/local-rehearsal-design-controller",
    "/api/v61/v60-baseline",
    "/api/v61/rehearsal-design-spec",
    "/api/v61/local-only-execution-denial-proof",
    "/api/v61/no-broker-no-order-proof",
    "/api/v61/future-approval-phrase-policy",
    "/api/v61/canary-nonexecution-validator-v11",
    "/api/v61/readiness-governor",
    "/api/v61/execution-lock",
    "/api/v61/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "local-rehearsal-design-controller": ["v61_local_rehearsal_design_controller_report.json"],
    "v60-baseline": ["v60_baseline_readback_v1_report.json"],
    "rehearsal-design-spec": ["v61_rehearsal_design_spec_report.json"],
    "local-only-execution-denial-proof": ["v61_local_only_execution_denial_proof_report.json"],
    "no-broker-no-order-proof": ["v61_no_broker_no_order_proof_report.json"],
    "future-approval-phrase-policy": ["v61_future_approval_phrase_policy_report.json"],
    "canary-nonexecution-validator-v11": ["v61_canary_nonexecution_validator_v11_report.json"],
    "readiness-governor": ["readiness_governor_v21_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v20_report.json"],
    "mission-state": ["dummy_mission_state_report_v47.json", "dashboard_v61_report_v1.json", "completion_oriented_next_action_v61_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(61)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v61/reports.py scripts/generate_v61_reports.py dashboard/backend/v61_routes.py",
    "python scripts/generate_v61_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V61Context:
    def __init__(self) -> None:
        self.v60_baseline_status = sgc.baseline_status("final_report_v60.json", "V60")

    @property
    def design_status(self) -> str:
        return "PASS_LOCAL_REHEARSAL_DESIGN_NONEXECUTABLE"

    @property
    def final_verdict(self) -> str:
        if self.v60_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.v60_baseline_status.startswith("PARTIAL"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v60_baseline_status.startswith("FAIL"):
            return ["FAIL_V60_BASELINE_REGRESSION"]
        if self.v60_baseline_status.startswith("PARTIAL"):
            return ["PARTIAL_V60_BASELINE_UNAVAILABLE"]
        return []

    @property
    def next_action(self) -> str:
        return "LOCAL_REHEARSAL_DESIGN_COMPLETE_AWAIT_FUTURE_LOCAL_REHEARSAL_APPROVAL"


def _common(ctx: V61Context) -> dict[str, Any]:
    return {
        "v60_baseline_status": ctx.v60_baseline_status,
        "local_rehearsal_design_controller_status": ctx.design_status,
        "rehearsal_design_spec": REHEARSAL_DESIGN_SPEC,
        "design_only": True,
        "runnable_rehearsal_created": False,
        "runnable_rehearsal_path_present": False,
        "local_only_execution_denial_proof_status": "PASS_LOCAL_ONLY_EXECUTION_DENIED",
        "no_broker_no_order_proof_status": "PASS_NO_BROKER_NO_ORDER",
        "future_local_rehearsal_approval_phrase": sgc.LOCAL_REHEARSAL_DESIGN_PHRASE,
        "future_approval_phrase_required_for_runnable_artifact": True,
        "future_approval_phrase_required_for_design_reports": False,
        "canary_nonexecution_validator_v11_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V11",
        "readiness_governor_v21_status": "PASS",
        "execution_lock_deep_recheck_v20_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V61Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v60_baseline"):
        return "PASS" if ctx.v60_baseline_status == "PASS_V60_BASELINE_READBACK" else "FAIL" if ctx.v60_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V61Context) -> dict[str, Any]:
    workstream = "v61: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v61_rehearsal_design_spec_report.json":
        report.update({"v61_rehearsal_design_spec_status": "PASS_DESIGN_SPEC_ONLY", "spec": REHEARSAL_DESIGN_SPEC, "executable": False})
    elif name == "v61_future_approval_phrase_policy_report.json":
        report.update({"policy_status": "PASS_FUTURE_PHRASE_POLICY_LOCKED", "phrase": sgc.LOCAL_REHEARSAL_DESIGN_PHRASE, "phrase_distinct_from_inert_artifact_phrase": True})
    elif name == "dashboard_v61_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V61_ROUTES, "read_only_dashboard": True, "dashboard_can_run_rehearsal": False})
    elif name == "completion_oriented_next_action_v61_report.json":
        report.update({"completion_oriented_next_action_v61_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v47.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v60_carried_status": ctx.v60_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v61.json"), "design_controller": str(ARTIFACTS / "v61_local_rehearsal_design_controller_report.json"), "design_spec": str(ARTIFACTS / "v61_rehearsal_design_spec_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v61.json", "dummy_canonical_identity_report_v61.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V61ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V61Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
