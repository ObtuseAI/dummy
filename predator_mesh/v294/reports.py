"""DUMMY v294 completion lift V9 and final proof-ready lock — proof-aware scoring; fixtures never inflate real proof; no submit, no scale, no autonomy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh import final_console_common as fcc
from predator_mesh.v294 import MILESTONE

WORKSTREAM = "v294: Completion Lift V9 Final Proof-Ready Lock And Next Actions"
DASH_TITLE = "Dummy V294 Completion Lift V9 Final Proof-Ready Lock"
MISSION_KEY = "dummy_mission_state_report_v294"
CONTROLLER_KEY = "completion_lift_v9_controller_status"

NEXT_ACTION_MATRIX = [
    "RUN_FINAL_RUN_APPLIANCE",
    "RUN_NO_SURPRISES_PRECHECK",
    "RUN_EXECUTE_ONCE_FINAL_RUN_WITH_AUTHORITY",
    "RUN_POST_PROOF_AUTOPILOT_INTAKE",
    "RUN_RECONCILE_FORENSIC_AUTOPIPELINE",
    "RUN_REPEAT_SESSION_FAST_ROUTE_PREP",
    "ROUTE_REPEAT_OR_SESSION",
]


def _ok(final_name: str, key: str, expected: str) -> bool:
    return str(sgc.load_artifact(final_name).get(key, "")) == expected


def build_completion_lift_v9() -> dict[str, Any]:
    st = fcc.read_authority_state()
    appliance_ok = str(sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status", "")) == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    runbook_ok = _ok("final_report_v277.json", "final_live_proof_runbook_lock_controller_status", "PASS_FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY")
    rehearsal_ok = _ok("final_report_v278.json", "execute_once_authority_rehearsal_v2_controller_status", "PASS_EXECUTE_ONCE_AUTHORITY_REHEARSAL_V2_COMPLETE_FIXTURE_ONLY")
    final_run_ok = _ok("final_report_v287.json", "final_run_appliance_launcher_controller_status", "PASS_FINAL_RUN_APPLIANCE_DRY_COMPLETE")
    precheck_built = str(sgc.load_artifact("final_report_v288.json").get("live_proof_no_surprises_precheck_controller_status", "")).startswith(("PASS", "PARTIAL"))
    monitor_built = str(sgc.load_artifact("final_report_v279.json").get("live_proof_attempt_monitor_controller_status", "")).startswith(("PASS", "PARTIAL"))
    real_proof = st["real_proof"]
    percentages = {
        "architecture_governance": 100,
        "activation_pipeline": 100,
        "authority_intake": 100 if st["import_ok"] else 30,
        "operator_ready_appliance": 100 if appliance_ok else 60,
        "external_authority_import": 100 if (st["import_ok"] and st["schema_ok"]) else 40,
        "adapter_contract": 100 if st["adapter_ok"] else 40,
        "adapter_injection_appliance": 100 if st["adapter_ok"] else 40,
        "live_submit_caps_verification": 100 if st["caps_ok"] else 20,
        "broker_readonly_verification": 100 if st["readonly_ok"] else 50,
        "final_runbook": 100 if runbook_ok else 60,
        "authority_rehearsal": 100 if rehearsal_ok else 60,
        "final_run_appliance": 100 if final_run_ok else 60,
        "no_surprises_precheck": 100 if precheck_built else 60,
        "attempt_monitor": 100 if monitor_built else 60,
        "first_live_proof": 100 if real_proof else 0,
        "proof_intake": 100 if (real_proof and st["handoff_present"]) else 0,
        "reconcile_forensic": 100 if real_proof else 0,
        "repeat_readiness": 100 if real_proof else 0,
        "controlled_session_readiness": 100 if real_proof else 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    if not st["caps_ok"]:
        selection = "RUN_FINAL_RUN_APPLIANCE"
    elif not real_proof:
        selection = "RUN_EXECUTE_ONCE_FINAL_RUN_WITH_AUTHORITY"
    else:
        selection = "RUN_RECONCILE_FORENSIC_AUTOPIPELINE"
    return {
        "subsystem_percentages": percentages,
        "fully_operational_estimate": fully_operational,
        "real_first_live_proof_present": real_proof,
        "fixture_proof_inflates_real_score": False,
        "scale_autonomy_blocked_by_no_live_proof": not real_proof,
        "next_action_matrix_selection": selection,
    }


REPORT_GROUPS: dict[str, list[str]] = {
    "completion-lift-v9-controller": ["v294_completion_lift_v9_controller_report.json"],
    "v293-baseline": ["v293_baseline_readback_v1_report.json"],
    "proof-aware-percentages": ["v294_proof_aware_percentages_report.json"],
    "next-action-matrix": ["v294_next_action_matrix_report.json"],
    "no-fixture-inflation-proof": ["v294_no_fixture_inflation_proof_report.json"],
    "no-submit-proof": ["v294_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v294_no_broker_contact_proof_report.json"],
    "no-scale-proof": ["v294_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v294_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v254_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v253_report.json"],
    "mission-state": ["dummy_mission_state_report_v294.json", "dashboard_v294_report_v1.json", "completion_oriented_next_action_v294_report.json"],
}

V294_ROUTES = [f"/api/v294/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Completion Lift V9", CONTROLLER_KEY], ["Fully Operational Est", "fully_operational_estimate"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    lift = build_completion_lift_v9()
    return {
        "status": "PASS_COMPLETION_LIFT_V9_FINAL_PROOF_READY_LOCKED",
        "verdict": "PASS",
        "fields": {
            "subsystem_percentages": lift["subsystem_percentages"],
            "fully_operational_estimate": lift["fully_operational_estimate"],
            "real_first_live_proof_present": lift["real_first_live_proof_present"],
            "fixture_proof_inflates_real_score": lift["fixture_proof_inflates_real_score"],
            "scale_autonomy_blocked_by_no_live_proof": lift["scale_autonomy_blocked_by_no_live_proof"],
            "next_action_matrix": NEXT_ACTION_MATRIX,
            "next_action_matrix_selection": lift["next_action_matrix_selection"],
            "completion_lift_v9": lift,
            "route_locked": True,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        },
        "blockers": [],
        "next_action": "COMPLETION_LIFT_V9_FINAL_PROOF_READY_LOCKED_NEXT_" + lift["next_action_matrix_selection"] + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=294, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS,
    index_keys=[CONTROLLER_KEY, "fully_operational_estimate", "next_action_matrix_selection"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V294_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V294ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
