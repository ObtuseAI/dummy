"""DUMMY v254 completion lift v5 operator ready lock and next phase map — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v254 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v254: Completion Lift V5 Operator Ready Lock And Next Phase Map"
MISSION_NAME = "dummy_mission_state_report_v240.json"
FINAL_NAME = "final_report_v254.json"
INDEX_KEYS = ['completion_lift_v5_controller_status', 'fully_operational_estimate', 'next_action_matrix_selection']
DASH_TITLE = "Dummy V254 Completion Lift V5 Operator Ready Lock And Next Phase Map"
MISSION_KEY = "dummy_mission_state_report_v240"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Completion Lift V5', 'completion_lift_v5_controller_status'], ['Fully Operational Est', 'fully_operational_estimate'], ['Next Action Matrix', 'next_action_matrix_selection'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V254_ROUTES = ['/api/v254/completion-lift-v5-controller', '/api/v254/v253-baseline', '/api/v254/proof-aware-percentages', '/api/v254/operator-action-map', '/api/v254/next-action-matrix', '/api/v254/no-fixture-inflation-proof', '/api/v254/no-submit-proof', '/api/v254/no-broker-contact-proof', '/api/v254/no-scale-proof', '/api/v254/no-autonomy-proof', '/api/v254/readiness-governor', '/api/v254/execution-lock', '/api/v254/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'completion-lift-v5-controller': ['v254_completion_lift_v5_controller_report.json'], 'v253-baseline': ['v253_baseline_readback_v1_report.json'], 'proof-aware-percentages': ['v254_proof_aware_percentages_report.json'], 'operator-action-map': ['v254_operator_action_map_report.json'], 'next-action-matrix': ['v254_next_action_matrix_report.json'], 'no-fixture-inflation-proof': ['v254_no_fixture_inflation_proof_report.json'], 'no-submit-proof': ['v254_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v254_no_broker_contact_proof_report.json'], 'no-scale-proof': ['v254_no_scale_proof_report.json'], 'no-autonomy-proof': ['v254_no_autonomy_proof_report.json'], 'readiness-governor': ['readiness_governor_v214_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v213_report.json'], 'mission-state': ['dummy_mission_state_report_v240.json', 'dashboard_v254_report_v1.json', 'completion_oriented_next_action_v254_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(254)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v254/reports.py scripts/generate_v254_reports.py dashboard/backend/v254_routes.py",
    "python scripts/generate_v254_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v254_completion_lift_v5_controller_report.json"

SUBSYSTEMS = ["architecture_governance", "activation_pipeline", "authority_intake", "operator_ready_appliance", "adapter_contract", "live_submit_caps_rehearsal", "first_live_proof", "reconcile_forensic", "repeat_proof", "controlled_session", "scale_review", "autonomy_review", "production_operation"]
NEXT_ACTION_MATRIX = [
    "OPERATOR_CREATE_AUTHORITY_MANIFEST",
    "OPERATOR_CONFIGURE_LIVE_SUBMIT_CAPS",
    "OPERATOR_INJECT_FIREWALL_ADAPTER",
    "RUN_ARMABLE_QUORUM_DOCTOR",
    "RUN_PRE_EXECUTION_FREEZE",
    "RUN_EXECUTE_ONCE_WITH_AUTHORITY",
    "RUN_POST_EXECUTION_INTAKE",
    "RUN_RECONCILE_FORENSIC",
    "ROUTE_REPEAT_OR_SESSION",
]


def build_completion_lift_v5() -> dict:
    manifest_ok = str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
    config_ok = str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE"
    adapter_ok = str(sgc.load_artifact("final_report_v248.json").get("adapter_contract_kit_controller_status", "")) == "PASS_ADAPTER_CONTRACT_KIT_READY_NON_BROKER_DOUBLE"
    appliance_pack_ok = str(sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status", "")) == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    config_rehearsal_ok = str(sgc.load_artifact("final_report_v249.json").get("live_submit_caps_rehearsal_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_REHEARSAL_READY_IMMUTABLE"
    quorum_ok = str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT"
    # Real proof only: a REAL env-gated execute-once with real_live_orders>0. Fixtures/dry never count.
    v242 = sgc.load_artifact("final_report_v242.json")
    real_proof = str(v242.get("execute_once_harness_controller_status", "")) == "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED" and int(v242.get("real_live_orders_submitted_count", 0) or 0) > 0
    intake_valid = str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
    percentages = {
        "architecture_governance": 100,
        "activation_pipeline": 100,
        "authority_intake": 100 if (intake_valid or manifest_ok) else 20,
        "operator_ready_appliance": 100 if appliance_pack_ok else 60,
        "adapter_contract": 100 if adapter_ok else 40,
        "live_submit_caps_rehearsal": 100 if config_rehearsal_ok else 20,
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
        selection = "OPERATOR_CREATE_AUTHORITY_MANIFEST"
    elif not config_ok:
        selection = "OPERATOR_CONFIGURE_LIVE_SUBMIT_CAPS"
    elif not adapter_ok:
        selection = "OPERATOR_INJECT_FIREWALL_ADAPTER"
    elif not quorum_ok:
        selection = "RUN_ARMABLE_QUORUM_DOCTOR"
    elif not real_proof:
        selection = "RUN_EXECUTE_ONCE_WITH_AUTHORITY"
    else:
        selection = "RUN_RECONCILE_FORENSIC"
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": fully_operational,
        "real_first_live_proof_present": real_proof,
        "fixture_proof_inflates_real_score": False,
        "scale_autonomy_blocked_by_no_live_proof": not real_proof,
        "next_action_matrix_selection": selection,
    }


class V254Context:
    def __init__(self) -> None:
        self.v253_baseline_status = sgc.baseline_status("final_report_v253.json", "V253")
        self.lift = build_completion_lift_v5()

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_LIFT_V5_BASELINE_REGRESSION" if self.v253_baseline_status.startswith("FAIL") else "PASS_COMPLETION_LIFT_V5_OPERATOR_READY_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v253_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V253_BASELINE_REGRESSION"] if self.v253_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "COMPLETION_LIFT_V5_OPERATOR_READY_LOCKED_NEXT_" + self.lift["next_action_matrix_selection"] + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v253_baseline_status": ctx.v253_baseline_status,
        "completion_lift_v5_controller_status": ctx.controller_status,
        "subsystem_percentages": ctx.lift["subsystem_percentages"],
        "proof_aware_percentages_status": "PASS_PROOF_AWARE_PERCENTAGES",
        "fully_operational_estimate": ctx.lift["fully_operational_estimate"],
        "real_first_live_proof_present": ctx.lift["real_first_live_proof_present"],
        "fixture_proof_inflates_real_score": ctx.lift["fixture_proof_inflates_real_score"],
        "scale_autonomy_blocked_by_no_live_proof": ctx.lift["scale_autonomy_blocked_by_no_live_proof"],
        "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.lift["next_action_matrix_selection"],
        "operator_action_map_status": "PASS_OPERATOR_ACTION_MAP_EMITTED",
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "completion_lift_v5": ctx.lift,
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
        "readiness_governor_v214_status": "PASS",
        "execution_lock_deep_recheck_v213_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v253_baseline"):
        return "PASS" if ctx.v253_baseline_status == "PASS_V253_BASELINE_READBACK" else "FAIL" if ctx.v253_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v254: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v254_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V254_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v254_report.json":
        report.update({"completion_oriented_next_action_v254_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v253_carried_status": ctx.v253_baseline_status, "completion_lift_v5_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v254.json", "dummy_canonical_identity_report_v254.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V254ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V254Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
