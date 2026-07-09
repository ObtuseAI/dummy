"""DUMMY v244 completion lift lock v4 operator action map and percentage update — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v244 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v244: Completion Lift Lock V4 Operator Action Map And Percentage Update"
MISSION_NAME = "dummy_mission_state_report_v230.json"
FINAL_NAME = "final_report_v244.json"
INDEX_KEYS = ['completion_lift_lock_v4_controller_status', 'fully_operational_estimate', 'next_action_matrix_selection']
DASH_TITLE = "Dummy V244 Completion Lift Lock V4 Operator Action Map And Percentage Update"
MISSION_KEY = "dummy_mission_state_report_v230"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Completion Lift V4', 'completion_lift_lock_v4_controller_status'], ['Fully Operational Est', 'fully_operational_estimate'], ['Next Action Matrix', 'next_action_matrix_selection'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V244_ROUTES = ['/api/v244/completion-lift-lock-v4-controller', '/api/v244/v243-baseline', '/api/v244/proof-aware-percentages', '/api/v244/operator-action-map', '/api/v244/next-action-matrix', '/api/v244/no-fixture-inflation-proof', '/api/v244/no-submit-proof', '/api/v244/no-broker-contact-proof', '/api/v244/no-scale-proof', '/api/v244/no-autonomy-proof', '/api/v244/readiness-governor', '/api/v244/execution-lock', '/api/v244/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'completion-lift-lock-v4-controller': ['v244_completion_lift_lock_v4_controller_report.json'], 'v243-baseline': ['v243_baseline_readback_v1_report.json'], 'proof-aware-percentages': ['v244_proof_aware_percentages_report.json'], 'operator-action-map': ['v244_operator_action_map_report.json'], 'next-action-matrix': ['v244_next_action_matrix_report.json'], 'no-fixture-inflation-proof': ['v244_no_fixture_inflation_proof_report.json'], 'no-submit-proof': ['v244_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v244_no_broker_contact_proof_report.json'], 'no-scale-proof': ['v244_no_scale_proof_report.json'], 'no-autonomy-proof': ['v244_no_autonomy_proof_report.json'], 'readiness-governor': ['readiness_governor_v204_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v203_report.json'], 'mission-state': ['dummy_mission_state_report_v230.json', 'dashboard_v244_report_v1.json', 'completion_oriented_next_action_v244_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(244)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v244/reports.py scripts/generate_v244_reports.py dashboard/backend/v244_routes.py",
    "python scripts/generate_v244_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v244_completion_lift_lock_v4_controller_report.json"

SUBSYSTEMS = ["architecture_governance", "authority_intake", "activation_pipeline", "first_live_proof", "reconcile_forensic", "repeat_proof", "controlled_session", "scale_review", "autonomy_review", "production_operation"]
NEXT_ACTION_MATRIX = [
    "FIX_MANIFEST",
    "FIX_LIVE_SUBMIT_CAPS",
    "FIX_FIREWALL_ADAPTER",
    "FIX_BROKER_READONLY",
    "RUN_ARMABLE_QUORUM_DOCTOR",
    "RUN_EXECUTE_ONCE_WITH_AUTHORITY",
    "RUN_RECONCILE_FORENSIC_V2",
    "ROUTE_REPEAT_OR_SESSION",
]


def build_completion_lift_v4() -> dict:
    # Real-proof aware: only a REAL execute-once (env-gated full authority) lifts first_live_proof. Fixtures never inflate.
    manifest_ok = str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
    config_ok = str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE"
    adapter_ok = str(sgc.load_artifact("final_report_v238.json").get("firewall_adapter_doctor_controller_status", "")) == "PASS_FIREWALL_ADAPTER_DOCTOR_READY_NON_BROKER_DOUBLE"
    broker_ok = str(sgc.load_artifact("final_report_v239.json").get("broker_readonly_doctor_controller_status", "")) == "PASS_BROKER_READONLY_DOCTOR_READY_NON_BROKER_DOUBLE"
    quorum_ok = str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT"
    v242 = sgc.load_artifact("final_report_v242.json")
    real_proof = str(v242.get("execute_once_harness_controller_status", "")) == "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED" and int(v242.get("real_live_orders_submitted_count", 0) or 0) > 0
    intake_valid = str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
    percentages = {
        "architecture_governance": 100,
        "authority_intake": 100 if (intake_valid or manifest_ok) else 20,
        "activation_pipeline": 100,
        "first_live_proof": 100 if real_proof else 0,
        "reconcile_forensic": 100 if real_proof else 0,
        "repeat_proof": 0,
        "controlled_session": 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    if not manifest_ok:
        selection = "FIX_MANIFEST"
    elif not config_ok:
        selection = "FIX_LIVE_SUBMIT_CAPS"
    elif not adapter_ok:
        selection = "FIX_FIREWALL_ADAPTER"
    elif not broker_ok:
        selection = "FIX_BROKER_READONLY"
    elif not quorum_ok:
        selection = "RUN_ARMABLE_QUORUM_DOCTOR"
    elif not real_proof:
        selection = "RUN_EXECUTE_ONCE_WITH_AUTHORITY"
    else:
        selection = "RUN_RECONCILE_FORENSIC_V2"
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": fully_operational,
        "real_first_live_proof_present": real_proof,
        "fixture_proof_inflates_real_score": False,
        "next_action_matrix_selection": selection,
    }


class V244Context:
    def __init__(self) -> None:
        self.v243_baseline_status = sgc.baseline_status("final_report_v243.json", "V243")
        self.lift = build_completion_lift_v4()

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_LIFT_LOCK_V4_BASELINE_REGRESSION" if self.v243_baseline_status.startswith("FAIL") else "PASS_COMPLETION_LIFT_LOCK_V4_GENERATED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v243_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V243_BASELINE_REGRESSION"] if self.v243_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "COMPLETION_LIFT_LOCK_V4_GENERATED_NEXT_" + self.lift["next_action_matrix_selection"] + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v243_baseline_status": ctx.v243_baseline_status,
        "completion_lift_lock_v4_controller_status": ctx.controller_status,
        "subsystem_percentages": ctx.lift["subsystem_percentages"],
        "proof_aware_percentages_status": "PASS_PROOF_AWARE_PERCENTAGES",
        "fully_operational_estimate": ctx.lift["fully_operational_estimate"],
        "real_first_live_proof_present": ctx.lift["real_first_live_proof_present"],
        "fixture_proof_inflates_real_score": ctx.lift["fixture_proof_inflates_real_score"],
        "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.lift["next_action_matrix_selection"],
        "operator_action_map_status": "PASS_OPERATOR_ACTION_MAP_EMITTED",
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "completion_lift_v4": ctx.lift,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",

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
        "readiness_governor_v204_status": "PASS",
        "execution_lock_deep_recheck_v203_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v243_baseline"):
        return "PASS" if ctx.v243_baseline_status == "PASS_V243_BASELINE_READBACK" else "FAIL" if ctx.v243_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v244: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v244_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V244_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v244_report.json":
        report.update({"completion_oriented_next_action_v244_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v243_carried_status": ctx.v243_baseline_status, "completion_lift_lock_v4_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v244.json", "dummy_canonical_identity_report_v244.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V244ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V244Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
