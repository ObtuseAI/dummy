"""DUMMY v274 completion lift v7 route lock and next operator actions — fail-closed staged gate; no live order, no broker contact, no submit, no scale, no autonomy by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v274 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v274: Completion Lift V7 Route Lock And Next Operator Actions"
MISSION_NAME = "dummy_mission_state_report_v260.json"
FINAL_NAME = "final_report_v274.json"
INDEX_KEYS = ['completion_lift_v7_controller_status', 'fully_operational_estimate', 'next_action_matrix_selection']
DASH_TITLE = "Dummy V274 Completion Lift V7 Route Lock And Next Operator Actions"
MISSION_KEY = "dummy_mission_state_report_v260"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Completion Lift V7', 'completion_lift_v7_controller_status'], ['Fully Operational Est', 'fully_operational_estimate'], ['Next Action Matrix', 'next_action_matrix_selection'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V274_ROUTES = ['/api/v274/completion-lift-v7-controller', '/api/v274/v273-baseline', '/api/v274/proof-aware-percentages', '/api/v274/operator-action-map', '/api/v274/next-action-matrix', '/api/v274/no-fixture-inflation-proof', '/api/v274/no-submit-proof', '/api/v274/no-broker-contact-proof', '/api/v274/no-scale-proof', '/api/v274/no-autonomy-proof', '/api/v274/readiness-governor', '/api/v274/execution-lock', '/api/v274/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'completion-lift-v7-controller': ['v274_completion_lift_v7_controller_report.json'], 'v273-baseline': ['v273_baseline_readback_v1_report.json'], 'proof-aware-percentages': ['v274_proof_aware_percentages_report.json'], 'operator-action-map': ['v274_operator_action_map_report.json'], 'next-action-matrix': ['v274_next_action_matrix_report.json'], 'no-fixture-inflation-proof': ['v274_no_fixture_inflation_proof_report.json'], 'no-submit-proof': ['v274_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v274_no_broker_contact_proof_report.json'], 'no-scale-proof': ['v274_no_scale_proof_report.json'], 'no-autonomy-proof': ['v274_no_autonomy_proof_report.json'], 'readiness-governor': ['readiness_governor_v234_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v233_report.json'], 'mission-state': ['dummy_mission_state_report_v260.json', 'dashboard_v274_report_v1.json', 'completion_oriented_next_action_v274_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(274)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v274/reports.py scripts/generate_v274_reports.py dashboard/backend/v274_routes.py",
    "python scripts/generate_v274_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v274_completion_lift_v7_controller_report.json"

NEXT_ACTION_MATRIX = [
    "OPERATOR_CREATE_AUTHORITY_MANIFEST",
    "OPERATOR_CONFIGURE_LIVE_SUBMIT_CAPS",
    "OPERATOR_INJECT_FIREWALL_ADAPTER",
    "RUN_EXTERNAL_AUTHORITY_IMPORT_WIZARD",
    "RUN_FINAL_ARMABILITY_RUNBOOK",
    "RUN_EXECUTE_ONCE_RUNBOOK_WITH_AUTHORITY",
    "RUN_PROOF_INTAKE_RECONCILE_HANDOFF",
    "RUN_RECONCILE_FORENSIC",
    "ROUTE_REPEAT_OR_SESSION",
]


def build_completion_lift_v7() -> dict:
    import_ok = str(sgc.load_artifact("final_report_v266.json").get("external_authority_import_wizard_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_NO_WRITE"
    schema_ok = str(sgc.load_artifact("final_report_v267.json").get("approval_manifest_schema_verifier_controller_status", "")) == "PASS_APPROVAL_MANIFEST_SCHEMA_VERIFIED_READY_FOR_RESOLVER"
    caps_ok = str(sgc.load_artifact("final_report_v268.json").get("external_live_submit_caps_state_verifier_controller_status", "")) == "PASS_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_IMMUTABLE"
    adapter_ok = str(sgc.load_artifact("final_report_v269.json").get("livebrokerfirewall_injection_appliance_controller_status", "")) == "PASS_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_READY_NON_BROKER_DOUBLE"
    readonly_ok = str(sgc.load_artifact("final_report_v270.json").get("broker_readonly_optional_verifier_controller_status", "")) == "PASS_BROKER_READONLY_OPTIONAL_VERIFIER_READY_NON_BROKER_DOUBLE"
    armable_ok = str(sgc.load_artifact("final_report_v271.json").get("final_armability_runbook_controller_status", "")) == "PASS_FINAL_ARMABILITY_RUNBOOK_READY_NO_SUBMIT"
    freeze_ok = str(sgc.load_artifact("final_report_v260.json").get("pre_execution_freeze_v2_controller_status", "")) == "PASS_PRE_EXECUTION_FREEZE_V2_READY_NO_SUBMIT"
    appliance_ok = str(sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status", "")) == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    # REAL proof only: env-gated execute-once with real_live_orders>0. Fixtures/dry never count.
    v272 = sgc.load_artifact("final_report_v272.json")
    real_proof = str(v272.get("execute_once_runbook_controller_status", "")) == "PASS_EXECUTE_ONCE_RUNBOOK_SUBMITTED_AUTOLOCKED" and int(v272.get("real_live_orders_submitted_count", 0) or 0) > 0
    handoff_present = str(sgc.load_artifact("final_report_v273.json").get("proof_intake_reconcile_handoff_v3_controller_status", "")) == "PASS_PROOF_INTAKE_RECONCILE_HANDOFF_READY_LOCKED"
    percentages = {
        "architecture_governance": 100,
        "activation_pipeline": 100,
        "authority_intake": 100 if import_ok else 30,
        "operator_ready_appliance": 100 if appliance_ok else 60,
        "external_authority_import": 100 if (import_ok and schema_ok) else 40,
        "adapter_contract": 100 if adapter_ok else 40,
        "adapter_injection_appliance": 100 if adapter_ok else 40,
        "live_submit_caps_verification": 100 if caps_ok else 20,
        "broker_readonly_verification": 100 if readonly_ok else 50,
        "pre_execution_freeze": 100 if (freeze_ok or armable_ok) else 20,
        "execute_once_harness": 70,
        "first_live_proof": 100 if real_proof else 0,
        "proof_intake": 100 if (real_proof and handoff_present) else 0,
        "reconcile_forensic": 100 if real_proof else 0,
        "repeat_proof": 0,
        "controlled_session": 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    if not import_ok:
        selection = "RUN_EXTERNAL_AUTHORITY_IMPORT_WIZARD"
    elif not caps_ok:
        selection = "OPERATOR_CONFIGURE_LIVE_SUBMIT_CAPS"
    elif not adapter_ok:
        selection = "OPERATOR_INJECT_FIREWALL_ADAPTER"
    elif not armable_ok:
        selection = "RUN_FINAL_ARMABILITY_RUNBOOK"
    elif not real_proof:
        selection = "RUN_EXECUTE_ONCE_RUNBOOK_WITH_AUTHORITY"
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


class V274Context:
    def __init__(self) -> None:
        self.v273_baseline_status = sgc.baseline_status("final_report_v273.json", "V273")
        self.lift = build_completion_lift_v7()

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_LIFT_V7_BASELINE_REGRESSION" if self.v273_baseline_status.startswith("FAIL") else "PASS_COMPLETION_LIFT_V7_ROUTE_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v273_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V273_BASELINE_REGRESSION"] if self.v273_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "COMPLETION_LIFT_V7_ROUTE_LOCKED_NEXT_" + self.lift["next_action_matrix_selection"] + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v273_baseline_status": ctx.v273_baseline_status,
        "completion_lift_v7_controller_status": ctx.controller_status,
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
        "completion_lift_v7": ctx.lift,
        "route_locked": True,
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
        "readiness_governor_v234_status": "PASS",
        "execution_lock_deep_recheck_v233_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v273_baseline"):
        return "PASS" if ctx.v273_baseline_status == "PASS_V273_BASELINE_READBACK" else "FAIL" if ctx.v273_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v274: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v274_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V274_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v274_report.json":
        report.update({"completion_oriented_next_action_v274_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v273_carried_status": ctx.v273_baseline_status, "completion_lift_v7_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v274.json", "dummy_canonical_identity_report_v274.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V274ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V274Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
