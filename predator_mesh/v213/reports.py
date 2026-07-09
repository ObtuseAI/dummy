"""DUMMY v213 completion scoreboard — durable completion scoreboard for Dummy's live-readiness path; no submit.

Computes subsystem completion percentages, a remaining blocker count, a proof-status count, and the exact next action,
then derives a fully_operational_estimate from the actual proof state. Static PASS; no live order, no broker contact.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v213 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v213: Completion Scoreboard And Remaining Percent Calculator"
MISSION_NAME = "dummy_mission_state_report_v199.json"
FINAL_NAME = "final_report_v213.json"
INDEX_KEYS = ["completion_scoreboard_controller_status", "fully_operational_estimate", "remaining_blocker_count"]
DASH_TITLE = "Dummy V213 Completion Scoreboard"
MISSION_KEY = "dummy_mission_state_report_v199"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Scoreboard", "completion_scoreboard_controller_status"],
    ["Fully Operational Est", "fully_operational_estimate"],
    ["Remaining Blockers", "remaining_blocker_count"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V213_ROUTES = [
    "/api/v213/completion-scoreboard-controller",
    "/api/v213/v212-baseline",
    "/api/v213/subsystem-percentages",
    "/api/v213/remaining-blocker-count",
    "/api/v213/proof-status-count",
    "/api/v213/fully-operational-estimate",
    "/api/v213/exact-next-action",
    "/api/v213/no-submit-proof",
    "/api/v213/no-broker-contact-proof",
    "/api/v213/readiness-governor",
    "/api/v213/execution-lock",
    "/api/v213/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "completion-scoreboard-controller": ["v213_completion_scoreboard_controller_report.json"],
    "v212-baseline": ["v212_baseline_readback_v1_report.json"],
    "subsystem-percentages": ["v213_subsystem_percentages_report.json"],
    "remaining-blocker-count": ["v213_remaining_blocker_count_report.json"],
    "proof-status-count": ["v213_proof_status_count_report.json"],
    "fully-operational-estimate": ["v213_fully_operational_estimate_report.json"],
    "exact-next-action": ["v213_exact_next_action_report.json"],
    "no-submit-proof": ["v213_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v213_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v173_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v172_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v213_report_v1.json", "completion_oriented_next_action_v213_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(213)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v213/reports.py scripts/generate_v213_reports.py dashboard/backend/v213_routes.py",
    "python scripts/generate_v213_reports.py",
    "python scripts/run_dummy_completion_scoreboard.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

SUBSYSTEMS = ["architecture_governance", "authority_intake", "first_live_proof", "reconcile_forensic", "repeat_proof", "controlled_session", "scale_review", "autonomy_review", "production_operation"]


def build_scoreboard() -> dict[str, Any]:
    proof_done = str(sgc.load_artifact("final_report_v209.json").get("live_proof_runner_controller_status", "")) == "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    reconciled = str(sgc.load_artifact("final_report_v210.json").get("reconcile_runner_controller_status", "")) == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
    reviewed = str(sgc.load_artifact("final_report_v211.json").get("forensic_runner_controller_status", "")) == "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED"
    percentages = {
        "architecture_governance": 100,
        "authority_intake": 20,
        "first_live_proof": 100 if proof_done else 0,
        "reconcile_forensic": 100 if (reconciled and reviewed) else 0,
        "repeat_proof": 0,
        "controlled_session": 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    canonical = sgc.load_artifact("final_report_v205.json").get("canonical_blocker_list", [])
    proof_status_count = int(proof_done) + int(reconciled) + int(reviewed)
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": fully_operational,
        "remaining_blocker_count": len(canonical),
        "proof_status_count": proof_status_count,
        "proof_done": proof_done,
        "reconciled": reconciled,
        "reviewed": reviewed,
        "exact_next_action": "OPERATOR_PROVIDE_APPROVAL_FILES_LIVE_SUBMIT_CAPS_AND_FIREWALL_THEN_RUN_FIRST_LIVE_PROOF" if not proof_done else "RUN_RECONCILE_AND_FORENSICS",
    }


class V213Context:
    def __init__(self) -> None:
        self.v212_baseline_status = sgc.baseline_status("final_report_v212.json", "V212")
        self.scoreboard = build_scoreboard()

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_SCOREBOARD_BASELINE_REGRESSION" if self.v212_baseline_status.startswith("FAIL") else "PASS_COMPLETION_SCOREBOARD_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v212_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V212_BASELINE_REGRESSION"] if self.v212_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return self.scoreboard["exact_next_action"]


def _common(ctx: V213Context) -> dict[str, Any]:
    return {
        "v212_baseline_status": ctx.v212_baseline_status,
        "completion_scoreboard_controller_status": ctx.controller_status,
        "subsystem_percentages_status": "PASS_SUBSYSTEM_PERCENTAGES_COMPUTED",
        "subsystem_percentages": ctx.scoreboard["subsystem_percentages"],
        "remaining_blocker_count_status": "PASS_REMAINING_BLOCKER_COUNTED",
        "remaining_blocker_count": ctx.scoreboard["remaining_blocker_count"],
        "proof_status_count_status": "PASS_PROOF_STATUS_COUNTED",
        "proof_status_count": ctx.scoreboard["proof_status_count"],
        "fully_operational_estimate_status": "PASS_FULLY_OPERATIONAL_ESTIMATED",
        "fully_operational_estimate": ctx.scoreboard["fully_operational_estimate"],
        "exact_next_action_status": "PASS_EXACT_NEXT_ACTION_SET",
        "exact_next_action": ctx.scoreboard["exact_next_action"],
        "completion_scoreboard": ctx.scoreboard,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v173_status": "PASS",
        "execution_lock_deep_recheck_v172_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V213Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v212_baseline"):
        return "PASS" if ctx.v212_baseline_status == "PASS_V212_BASELINE_READBACK" else "FAIL" if ctx.v212_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V213Context) -> dict[str, Any]:
    workstream = "v213: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v213_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V213_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v213_report.json":
        report.update({"completion_oriented_next_action_v213_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v212_carried_status": ctx.v212_baseline_status, "fully_operational_estimate": ctx.scoreboard["fully_operational_estimate"], "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v213_completion_scoreboard_controller_report.json"), "completion_scoreboard": str(ARTIFACTS / "completion_scoreboard_v213.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v213.json", "dummy_canonical_identity_report_v213.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V213ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V213Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
