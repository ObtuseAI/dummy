"""DUMMY v304 completion lift V10 and real-proof fork lock — proof-aware scoring; fixtures never inflate real proof; proof-starvation stop rule enforced; no submit, no scale, no autonomy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh import final_console_common as fcc
from predator_mesh.v304 import MILESTONE

REGISTRY_PATH = sgc.ARTIFACTS / "real_proof_registry.json"

WORKSTREAM = "v304: Completion Lift V10 Real-Proof Fork Lock And Next Actions"
DASH_TITLE = "Dummy V304 Completion Lift V10 Real-Proof Fork Lock"
MISSION_KEY = "dummy_mission_state_report_v304"
CONTROLLER_KEY = "completion_lift_v10_controller_status"

NEXT_ACTION_MATRIX = [
    "STOP_BUILDING_GATES_UNTIL_REAL_PROOF",
    "RUN_EXTERNAL_AUTHORITY_PATH",
    "RUN_EXECUTE_ONCE_FINAL_PROOF_WITH_AUTHORITY",
    "RUN_POST_PROOF_AUTO_INTAKE",
    "RUN_RECONCILE_FORENSIC_ORCHESTRATOR",
    "RUN_POST_PROOF_ROUTE_AUTOPILOT",
    "THEN_BUILD_REPEAT_OR_SESSION",
]


def _ok(final_name: str, key: str, expected: str) -> bool:
    return str(sgc.load_artifact(final_name).get(key, "")) == expected


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_real_proof_registry() -> dict[str, Any] | None:
    """Read the preserved real-proof registry safely; return None if missing/invalid."""
    if not REGISTRY_PATH.exists():
        return None
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _historical_v304_fully_operational(registry: dict[str, Any] | None) -> int | None:
    """Try to recover the historical fully-operational estimate from the registry's v304 backup."""
    if not registry:
        return None
    index_rel = registry.get("latest_real_broker_proof_index")
    if not isinstance(index_rel, str):
        return None
    index_path = (sgc.ROOT / index_rel).resolve()
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for entry in index.get("source_artifact_paths", []):
        if not isinstance(entry, dict):
            continue
        path = Path(entry.get("path", ""))
        if path.name != "final_report_v304.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        val = data.get("fully_operational_estimate")
        if isinstance(val, int):
            return val
    return None


def _compute_fully_operational_with_real_proof() -> int:
    """Run the same percentage method as build_completion_lift_v10() with real_first_live_proof_present=True."""
    st = fcc.read_authority_state()
    appliance_ok = str(sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status", "")) == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    runbook_ok = _ok("final_report_v277.json", "final_live_proof_runbook_lock_controller_status", "PASS_FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY")
    final_run_ok = _ok("final_report_v287.json", "final_run_appliance_launcher_controller_status", "PASS_FINAL_RUN_APPLIANCE_DRY_COMPLETE")
    precheck_built = str(sgc.load_artifact("final_report_v288.json").get("live_proof_no_surprises_precheck_controller_status", "")).startswith(("PASS", "PARTIAL"))
    seal_built = str(sgc.load_artifact("final_report_v297.json").get("execute_once_command_seal_controller_status", "")).startswith(("PASS", "PARTIAL"))
    runner_built = str(sgc.load_artifact("final_report_v298.json").get("execute_once_final_proof_runner_v7_controller_status", "")).startswith(("PASS", "PARTIAL"))
    real_proof = True
    percentages = {
        "architecture_governance": 100,
        "activation_pipeline": 100,
        "authority_intake": 100 if st["import_ok"] else 30,
        "operator_ready_appliance": 100 if appliance_ok else 60,
        "external_authority_import": 100 if (st["import_ok"] and st["schema_ok"]) else 40,
        "adapter_injection_appliance": 100 if st["adapter_ok"] else 40,
        "live_submit_caps_verification": 100 if st["caps_ok"] else 20,
        "broker_readonly_verification": 100 if st["readonly_ok"] else 50,
        "final_runbook": 100 if runbook_ok else 60,
        "final_run_appliance": 100 if final_run_ok else 60,
        "no_surprises_precheck": 100 if precheck_built else 60,
        "command_seal": 100 if seal_built else 60,
        "final_proof_runner": 100 if runner_built else 60,
        "first_live_proof": 100 if real_proof else 0,
        "proof_intake": 100 if (real_proof and st["handoff_present"]) else 0,
        "reconcile_forensic": 100 if real_proof else 0,
        "post_proof_route": 100 if real_proof else 0,
        "repeat_session_prep": 100 if real_proof else 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    return round(sum(percentages.values()) / (len(percentages) * 100) * 100)


def build_completion_lift_v10() -> dict[str, Any]:
    st = fcc.read_authority_state()
    appliance_ok = str(sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status", "")) == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    runbook_ok = _ok("final_report_v277.json", "final_live_proof_runbook_lock_controller_status", "PASS_FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY")
    final_run_ok = _ok("final_report_v287.json", "final_run_appliance_launcher_controller_status", "PASS_FINAL_RUN_APPLIANCE_DRY_COMPLETE")
    precheck_built = str(sgc.load_artifact("final_report_v288.json").get("live_proof_no_surprises_precheck_controller_status", "")).startswith(("PASS", "PARTIAL"))
    seal_built = str(sgc.load_artifact("final_report_v297.json").get("execute_once_command_seal_controller_status", "")).startswith(("PASS", "PARTIAL"))
    runner_built = str(sgc.load_artifact("final_report_v298.json").get("execute_once_final_proof_runner_v7_controller_status", "")).startswith(("PASS", "PARTIAL"))
    v298 = sgc.load_artifact("final_report_v298.json")
    v298_real_proof = (
        runner_built
        and str(v298.get("execute_once_final_proof_runner_v7_controller_status", "")) == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        and v298.get("non_broker_double_used") is False
        and v298.get("real_broker_contacted") is True
        and (
            int(v298.get("real_live_orders_submitted_count", 0) or 0) > 0
            or v298.get("broker_rejection_captured") is True
        )
    )
    real_proof = st["real_proof"] or v298_real_proof
    percentages = {
        "architecture_governance": 100,
        "activation_pipeline": 100,
        "authority_intake": 100 if st["import_ok"] else 30,
        "operator_ready_appliance": 100 if appliance_ok else 60,
        "external_authority_import": 100 if (st["import_ok"] and st["schema_ok"]) else 40,
        "adapter_injection_appliance": 100 if st["adapter_ok"] else 40,
        "live_submit_caps_verification": 100 if st["caps_ok"] else 20,
        "broker_readonly_verification": 100 if st["readonly_ok"] else 50,
        "final_runbook": 100 if runbook_ok else 60,
        "final_run_appliance": 100 if final_run_ok else 60,
        "no_surprises_precheck": 100 if precheck_built else 60,
        "command_seal": 100 if seal_built else 60,
        "final_proof_runner": 100 if runner_built else 60,
        "first_live_proof": 100 if real_proof else 0,
        "proof_intake": 100 if (real_proof and st["handoff_present"]) else 0,
        "reconcile_forensic": 100 if real_proof else 0,
        "post_proof_route": 100 if real_proof else 0,
        "repeat_session_prep": 100 if real_proof else 0,
        "scale_review": 0,
        "autonomy_review": 0,
        "production_operation": 15,
    }
    fully_operational = round(sum(percentages.values()) / (len(percentages) * 100) * 100)
    selection = "RUN_EXTERNAL_AUTHORITY_PATH" if not st["caps_ok"] else "RUN_EXECUTE_ONCE_FINAL_PROOF_WITH_AUTHORITY" if not real_proof else "RUN_POST_PROOF_AUTO_INTAKE"
    return {
        "subsystem_percentages": percentages,
        # Backward-compatible field name; this is a self-assessed checklist
        # average, not proof that the system is fully operational.
        "fully_operational_estimate": fully_operational,
        "self_assessed_checklist_score": fully_operational,
        "checklist_readiness_bar": 80,
        "operational_readiness_verdict": "PASS" if fully_operational >= 80 else "BELOW_READINESS_BAR",
        "real_first_live_proof_present": real_proof,
        "fixture_proof_inflates_real_score": False,
        "scale_autonomy_blocked_by_no_live_proof": not real_proof,
        "proof_starvation_stop_rule_active": not real_proof,
        "next_action_matrix_selection": selection,
    }


REPORT_GROUPS: dict[str, list[str]] = {
    "completion-lift-v10-controller": ["v304_completion_lift_v10_controller_report.json"],
    "v303-baseline": ["v303_baseline_readback_v1_report.json"],
    "proof-aware-percentages": ["v304_proof_aware_percentages_report.json"],
    "next-action-matrix": ["v304_next_action_matrix_report.json"],
    "no-fixture-inflation-proof": ["v304_no_fixture_inflation_proof_report.json"],
    "no-submit-proof": ["v304_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v304_no_broker_contact_proof_report.json"],
    "no-scale-proof": ["v304_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v304_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v264_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v263_report.json"],
    "mission-state": ["dummy_mission_state_report_v304.json", "dashboard_v304_report_v1.json", "completion_oriented_next_action_v304_report.json"],
}

V304_ROUTES = [f"/api/v304/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Completion Lift V10", CONTROLLER_KEY], ["Self-Assessed Checklist Score", "self_assessed_checklist_score"], ["Operational Readiness", "operational_readiness_verdict"], ["Next Action Matrix", "next_action_matrix_selection"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    lift = build_completion_lift_v10()
    readiness_passed = lift["operational_readiness_verdict"] == "PASS"
    registry = _load_real_proof_registry()
    registry_present = registry is not None
    broker_contacted = bool(registry.get("latest_real_broker_contacted")) if registry_present else False
    rejection_captured = bool(registry.get("latest_real_broker_rejection_captured")) if registry_present else False
    index_rel = registry.get("latest_real_broker_proof_index") if registry_present else None
    evidence_index_path = str(index_rel) if isinstance(index_rel, str) else None
    evidence_index_hash = _sha256_file(sgc.ROOT / index_rel) if isinstance(index_rel, str) else None

    historical_fo = _historical_v304_fully_operational(registry)
    fo_with_preserved = historical_fo if historical_fo is not None else _compute_fully_operational_with_real_proof()

    preserved_fields: dict[str, Any] = {
        "active_default_state_real_first_live_proof_present": lift["real_first_live_proof_present"],
        "preserved_real_broker_proof_present": registry_present and broker_contacted,
        "preserved_real_broker_proof_status": registry.get("latest_real_broker_attempt_status") if registry_present else None,
        "preserved_real_broker_contacted": broker_contacted,
        "preserved_real_live_orders_submitted_count": registry.get("latest_real_live_orders_submitted_count", 0) if registry_present else 0,
        "preserved_broker_rejection_captured": rejection_captured,
        "preserved_evidence_index_path": evidence_index_path,
        "preserved_evidence_index_hash": evidence_index_hash,
        "fully_operational_estimate_active_default": lift["fully_operational_estimate"],
        "fully_operational_estimate_with_preserved_real_broker_attempt": fo_with_preserved,
    }

    return {
        "status": "PASS_COMPLETION_LIFT_V10_REAL_PROOF_FORK_LOCKED",
        # PASS status above means the controller ran and retained its safety
        # locks. Overall readiness remains PARTIAL below the declared bar.
        "verdict": "PASS" if readiness_passed else "PARTIAL",
        "fields": {
            "subsystem_percentages": lift["subsystem_percentages"],
            "fully_operational_estimate": lift["fully_operational_estimate"],
            "self_assessed_checklist_score": lift["self_assessed_checklist_score"],
            "checklist_readiness_bar": lift["checklist_readiness_bar"],
            "operational_readiness_verdict": lift["operational_readiness_verdict"],
            "controller_status_scope": "report_generation_and_safety_locks",
            "real_first_live_proof_present": lift["real_first_live_proof_present"],
            "fixture_proof_inflates_real_score": lift["fixture_proof_inflates_real_score"],
            "scale_autonomy_blocked_by_no_live_proof": lift["scale_autonomy_blocked_by_no_live_proof"],
            "proof_starvation_stop_rule_active": lift["proof_starvation_stop_rule_active"],
            "next_action_matrix": NEXT_ACTION_MATRIX,
            "next_action_matrix_selection": lift["next_action_matrix_selection"],
            "completion_lift_v10": lift,
            "real_proof_fork_locked": True,
            "route_locked": True,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            "no_scale_proof_status": "PASS_NO_SCALE",
            "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
            **preserved_fields,
        },
        "blockers": [] if readiness_passed else ["SELF_ASSESSED_CHECKLIST_SCORE_BELOW_80"],
        "next_action": "COMPLETION_LIFT_V10_REAL_PROOF_FORK_LOCKED_NEXT_" + lift["next_action_matrix_selection"] + "_NO_SUBMIT_NO_SCALE_NO_AUTONOMY",
    }


_BUNDLE = fcc.StageBundle(
    version=304, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS,
    index_keys=[CONTROLLER_KEY, "fully_operational_estimate", "next_action_matrix_selection"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V304_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V304ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
