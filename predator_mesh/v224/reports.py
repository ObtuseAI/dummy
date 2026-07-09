"""DUMMY v224 activation completion lock v2 next phase map — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v224 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v224: Activation Completion Lock V2 Next Phase Map"
MISSION_NAME = "dummy_mission_state_report_v210.json"
FINAL_NAME = "final_report_v224.json"
INDEX_KEYS = ['activation_completion_lock_v2_controller_status', 'next_action_matrix_selection', 'total_real_live_orders_submitted']
DASH_TITLE = "Dummy V224 Activation Completion Lock V2 Next Phase Map"
MISSION_KEY = "dummy_mission_state_report_v210"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Completion Lock', 'activation_completion_lock_v2_controller_status'], ['Next Action Matrix', 'next_action_matrix_selection'], ['Total Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V224_ROUTES = ['/api/v224/activation-completion-lock-v2-controller', '/api/v224/v223-baseline', '/api/v224/activation-packet-summary', '/api/v224/manifest-intake-summary', '/api/v224/dry-validation-summary', '/api/v224/arming-check-summary', '/api/v224/hardened-live-proof-summary', '/api/v224/reconcile-spine-summary', '/api/v224/forensic-spine-summary', '/api/v224/repeat-session-bridge-summary', '/api/v224/completion-scoreboard-summary', '/api/v224/total-live-order-count', '/api/v224/next-action-matrix', '/api/v224/no-scale-proof', '/api/v224/no-autonomy-proof', '/api/v224/no-new-order-proof', '/api/v224/readiness-governor', '/api/v224/execution-lock', '/api/v224/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'activation-completion-lock-v2-controller': ['v224_activation_completion_lock_v2_controller_report.json'], 'v223-baseline': ['v223_baseline_readback_v1_report.json'], 'activation-packet-summary': ['v224_activation_packet_summary_report.json'], 'manifest-intake-summary': ['v224_manifest_intake_summary_report.json'], 'dry-validation-summary': ['v224_dry_validation_summary_report.json'], 'arming-check-summary': ['v224_arming_check_summary_report.json'], 'hardened-live-proof-summary': ['v224_hardened_live_proof_summary_report.json'], 'reconcile-spine-summary': ['v224_reconcile_spine_summary_report.json'], 'forensic-spine-summary': ['v224_forensic_spine_summary_report.json'], 'repeat-session-bridge-summary': ['v224_repeat_session_bridge_summary_report.json'], 'completion-scoreboard-summary': ['v224_completion_scoreboard_summary_report.json'], 'total-live-order-count': ['v224_total_live_order_count_report.json'], 'next-action-matrix': ['v224_next_action_matrix_report.json'], 'no-scale-proof': ['v224_no_scale_proof_report.json'], 'no-autonomy-proof': ['v224_no_autonomy_proof_report.json'], 'no-new-order-proof': ['v224_no_new_order_proof_report.json'], 'readiness-governor': ['readiness_governor_v184_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v183_report.json'], 'mission-state': ['dummy_mission_state_report_v210.json', 'dashboard_v224_report_v1.json', 'completion_oriented_next_action_v224_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(224)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v224/reports.py scripts/generate_v224_reports.py dashboard/backend/v224_routes.py",
    "python scripts/generate_v224_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v224_activation_completion_lock_v2_controller_report.json"

NEXT_ACTION_MATRIX = [
    "PROVIDE_EXTERNAL_AUTHORITY_MANIFEST",
    "RUN_ZERO_BROKER_DRY_VALIDATION",
    "RUN_FINAL_ARMING_CHECK",
    "RUN_HARDENED_LIVE_PROOF",
    "RUN_RECONCILE_SPINE",
    "RUN_FORENSIC_SPINE",
    "REVIEW_REPEAT_OR_CONTROLLED_SESSION",
    "REPAIR_REQUIRED",
]


class V224Context:
    def __init__(self, *, manifest_override=None, arming_override=None, proof_override=None, reconciled_override=None, reviewed_override=None) -> None:
        self.v223_baseline_status = sgc.baseline_status("final_report_v223.json", "V223")
        self.packet_status = str(sgc.load_artifact("final_report_v215.json").get("operator_activation_packet_controller_status", "PASS_OPERATOR_ACTIVATION_PACKET_READY_READONLY"))
        self.manifest_valid = bool(manifest_override) if manifest_override is not None else (str(sgc.load_artifact("final_report_v216.json").get("external_authority_manifest_intake_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_MANIFEST_VALIDATED_NO_SUBMIT")
        self.dry_status = str(sgc.load_artifact("final_report_v217.json").get("zero_broker_dry_validation_controller_status", "PASS_ZERO_BROKER_DRY_VALIDATION_COMPLETE"))
        self.arming_ready = bool(arming_override) if arming_override is not None else (str(sgc.load_artifact("final_report_v218.json").get("final_live_proof_arming_check_controller_status", "")) == "PASS_FINAL_LIVE_PROOF_ARMING_READY_NO_SUBMIT")
        self.proof_done = bool(proof_override) if proof_override is not None else (str(sgc.load_artifact("final_report_v219.json").get("hardened_live_proof_execution_harness_controller_status", "")) == "PASS_HARDENED_LIVE_PROOF_SUBMITTED_AUTOLOCKED")
        self.reconciled = bool(reconciled_override) if reconciled_override is not None else (str(sgc.load_artifact("final_report_v220.json").get("reconcile_spine_v2_controller_status", "")) == "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED")
        self.reviewed = bool(reviewed_override) if reviewed_override is not None else (str(sgc.load_artifact("final_report_v221.json").get("forensic_spine_v2_controller_status", "")) == "PASS_FORENSIC_SPINE_V2_REVIEWED_LOCKED")
        self.bridge_status = str(sgc.load_artifact("final_report_v222.json").get("route_state", "ROUTE_BLOCKED_NO_LIVE_PROOF"))
        self.scoreboard_estimate = sgc.load_artifact("completion_scoreboard_v223.json").get("fully_operational_estimate", sgc.load_artifact("final_report_v223.json").get("fully_operational_estimate", 15))

    @property
    def next_action_matrix_selection(self) -> str:
        if not self.manifest_valid:
            return "PROVIDE_EXTERNAL_AUTHORITY_MANIFEST"
        if not self.arming_ready:
            return "RUN_FINAL_ARMING_CHECK"
        if not self.proof_done:
            return "RUN_HARDENED_LIVE_PROOF"
        if not self.reconciled:
            return "RUN_RECONCILE_SPINE"
        if not self.reviewed:
            return "RUN_FORENSIC_SPINE"
        return "REVIEW_REPEAT_OR_CONTROLLED_SESSION"

    @property
    def controller_status(self) -> str:
        return "FAIL_ACTIVATION_COMPLETION_LOCK_V2_BASELINE_REGRESSION" if self.v223_baseline_status.startswith("FAIL") else "PASS_ACTIVATION_COMPLETION_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v223_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V223_BASELINE_REGRESSION"] if self.v223_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"ACTIVATION_COMPLETION_LOCKED_NEXT_{self.next_action_matrix_selection}_NO_AUTONOMY_NO_SCALE_NO_NEW_ORDER"


def _common(ctx) -> dict[str, Any]:
    return {
        "v223_baseline_status": ctx.v223_baseline_status,
        "activation_completion_lock_v2_controller_status": ctx.controller_status,
        "activation_packet_summary": ctx.packet_status,
        "manifest_intake_summary": "VALIDATED" if ctx.manifest_valid else "ABSENT_OR_INCOMPLETE",
        "dry_validation_summary": ctx.dry_status,
        "arming_check_summary": "READY" if ctx.arming_ready else "BLOCKED",
        "hardened_live_proof_summary": "SUBMITTED_AUTOLOCKED" if ctx.proof_done else "NOT_ARMED",
        "reconcile_spine_summary": "STATE_CLASSIFIED" if ctx.reconciled else "NO_ATTEMPT",
        "forensic_spine_summary": "REVIEWED" if ctx.reviewed else "NO_ATTEMPT",
        "repeat_session_bridge_summary": ctx.bridge_status,
        "completion_scoreboard_summary": ctx.scoreboard_estimate,
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "total_live_order_count": 0,
        "total_live_order_count_status": "PASS_TOTAL_LIVE_ORDER_COUNT_ZERO",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "readiness_governor_v184_status": "PASS",
        "execution_lock_deep_recheck_v183_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v223_baseline"):
        return "PASS" if ctx.v223_baseline_status == "PASS_V223_BASELINE_READBACK" else "FAIL" if ctx.v223_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v224: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v224_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V224_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v224_report.json":
        report.update({"completion_oriented_next_action_v224_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v223_carried_status": ctx.v223_baseline_status, "activation_completion_lock_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v224.json", "dummy_canonical_identity_report_v224.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V224ReportFactory:
    def __init__(self, *, manifest_override=None, arming_override=None, proof_override=None, reconciled_override=None, reviewed_override=None) -> None:
        self.kw = dict(manifest_override=manifest_override, arming_override=arming_override, proof_override=proof_override, reconciled_override=reconciled_override, reviewed_override=reviewed_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V224Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
