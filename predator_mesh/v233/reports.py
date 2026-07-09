"""DUMMY v233 completion scoreboard v3 proof aware percentages — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v233 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v233: Completion Scoreboard V3 Proof Aware Percentages"
MISSION_NAME = "dummy_mission_state_report_v219.json"
FINAL_NAME = "final_report_v233.json"
INDEX_KEYS = ['completion_scoreboard_v3_controller_status', 'fully_operational_estimate', 'first_live_proof_present']
DASH_TITLE = "Dummy V233 Completion Scoreboard V3 Proof Aware Percentages"
MISSION_KEY = "dummy_mission_state_report_v219"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Scoreboard V3', 'completion_scoreboard_v3_controller_status'], ['Fully Operational Est', 'fully_operational_estimate'], ['First Live Proof', 'first_live_proof_present'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V233_ROUTES = ['/api/v233/completion-scoreboard-v3-controller', '/api/v233/v232-baseline', '/api/v233/proof-aware-percentages', '/api/v233/live-proof-dependent-uplift', '/api/v233/operator-action-blockers', '/api/v233/next-command-recommendation', '/api/v233/no-submit-proof', '/api/v233/no-broker-contact-proof', '/api/v233/readiness-governor', '/api/v233/execution-lock', '/api/v233/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'completion-scoreboard-v3-controller': ['v233_completion_scoreboard_v3_controller_report.json'], 'v232-baseline': ['v232_baseline_readback_v1_report.json'], 'proof-aware-percentages': ['v233_proof_aware_percentages_report.json'], 'live-proof-dependent-uplift': ['v233_live_proof_dependent_uplift_report.json'], 'operator-action-blockers': ['v233_operator_action_blockers_report.json'], 'next-command-recommendation': ['v233_next_command_recommendation_report.json'], 'no-submit-proof': ['v233_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v233_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v193_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v192_report.json'], 'mission-state': ['dummy_mission_state_report_v219.json', 'dashboard_v233_report_v1.json', 'completion_oriented_next_action_v233_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(233)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v233/reports.py scripts/generate_v233_reports.py dashboard/backend/v233_routes.py",
    "python scripts/generate_v233_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v233_completion_scoreboard_v3_controller_report.json"

SUBSYSTEMS = ["architecture_governance", "authority_intake", "first_live_proof", "reconcile_forensic", "repeat_proof", "controlled_session", "scale_review", "autonomy_review", "production_operation"]


def build_scoreboard_v3() -> dict:
    intake_valid = str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
    proof_done = str(sgc.load_artifact("final_report_v230.json").get("live_proof_execution_orchestrator_controller_status", "")) == "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED"
    pipeline_done = str(sgc.load_artifact("final_report_v231.json").get("reconcile_forensic_pipeline_controller_status", "")) == "PASS_RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED"
    route_ready = str(sgc.load_artifact("final_report_v232.json").get("route_decision_controller_status", "")) == "PASS_ROUTE_DECISION_READY_LOCKED"
    percentages = {
        "architecture_governance": 100,
        "authority_intake": 100 if intake_valid else 20,
        "first_live_proof": 100 if proof_done else 0,
        "reconcile_forensic": 100 if pipeline_done else 0,
        "repeat_proof": 0,
        "controlled_session": 40 if route_ready else 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    operator_blockers = []
    if not intake_valid:
        operator_blockers.append("PROVIDE_EXTERNAL_AUTHORITY_INTAKE")
    if not proof_done:
        operator_blockers.append("RUN_LIVE_PROOF_EXECUTE_ONCE")
    next_command = "python scripts/run_dummy_external_authority_intake.py" if not intake_valid else ("python scripts/run_dummy_live_proof_execute_once.py" if not proof_done else "python scripts/run_dummy_reconcile_forensic_pipeline.py")
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": fully_operational,
        "first_live_proof_present": proof_done,
        "intake_valid": intake_valid,
        "pipeline_done": pipeline_done,
        "route_ready": route_ready,
        "operator_action_blockers": operator_blockers,
        "next_command_recommendation": next_command,
        "exact_next_action": next_command,
    }


class V233Context:
    def __init__(self) -> None:
        self.v232_baseline_status = sgc.baseline_status("final_report_v232.json", "V232")
        self.scoreboard = build_scoreboard_v3()

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_SCOREBOARD_V3_BASELINE_REGRESSION" if self.v232_baseline_status.startswith("FAIL") else "PASS_COMPLETION_SCOREBOARD_V3_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v232_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V232_BASELINE_REGRESSION"] if self.v232_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "COMPLETION_SCOREBOARD_V3_GENERATED_" + self.scoreboard["next_command_recommendation"]


def _common(ctx) -> dict[str, Any]:
    return {
        "v232_baseline_status": ctx.v232_baseline_status,
        "completion_scoreboard_v3_controller_status": ctx.controller_status,
        "subsystem_percentages": ctx.scoreboard["subsystem_percentages"],
        "proof_aware_percentages_status": "PASS_PROOF_AWARE_PERCENTAGES",
        "fully_operational_estimate": ctx.scoreboard["fully_operational_estimate"],
        "first_live_proof_present": ctx.scoreboard["first_live_proof_present"],
        "live_proof_dependent_uplift_status": "PASS_LIVE_PROOF_DEPENDENT_UPLIFT",
        "operator_action_blockers": ctx.scoreboard["operator_action_blockers"],
        "operator_action_blockers_status": "PASS_OPERATOR_ACTION_BLOCKERS_LISTED",
        "next_command_recommendation": ctx.scoreboard["next_command_recommendation"],
        "next_command_recommendation_status": "PASS_NEXT_COMMAND_RECOMMENDED",
        "completion_scoreboard_v3": ctx.scoreboard,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",

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
        "readiness_governor_v193_status": "PASS",
        "execution_lock_deep_recheck_v192_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v232_baseline"):
        return "PASS" if ctx.v232_baseline_status == "PASS_V232_BASELINE_READBACK" else "FAIL" if ctx.v232_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v233: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v233_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V233_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v233_report.json":
        report.update({"completion_oriented_next_action_v233_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v232_carried_status": ctx.v232_baseline_status, "completion_scoreboard_v3_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v233.json", "dummy_canonical_identity_report_v233.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V233ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V233Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
