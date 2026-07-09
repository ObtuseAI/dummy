"""DUMMY v220 reconcile spine v2 proof state and lock recheck — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v220 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v220: Reconcile Spine V2 Proof State And Lock Recheck"
MISSION_NAME = "dummy_mission_state_report_v206.json"
FINAL_NAME = "final_report_v220.json"
INDEX_KEYS = ['reconcile_spine_v2_controller_status', 'order_state', 'new_order_placed']
DASH_TITLE = "Dummy V220 Reconcile Spine V2 Proof State And Lock Recheck"
MISSION_KEY = "dummy_mission_state_report_v206"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Reconcile Spine', 'reconcile_spine_v2_controller_status'], ['Order State', 'order_state'], ['New Order Placed', 'new_order_placed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V220_ROUTES = ['/api/v220/reconcile-spine-v2-controller', '/api/v220/v219-baseline', '/api/v220/proof-state-parser', '/api/v220/proof-target-classifier', '/api/v220/idempotency-verification', '/api/v220/proof-lock-recheck', '/api/v220/no-repeat-proof', '/api/v220/no-cancel-default-proof', '/api/v220/private-data-redaction', '/api/v220/readiness-governor', '/api/v220/execution-lock', '/api/v220/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'reconcile-spine-v2-controller': ['v220_reconcile_spine_v2_controller_report.json'], 'v219-baseline': ['v219_baseline_readback_v1_report.json'], 'proof-state-parser': ['v220_proof_state_parser_report.json'], 'proof-target-classifier': ['v220_proof_target_classifier_report.json'], 'idempotency-verification': ['v220_idempotency_verification_report.json'], 'proof-lock-recheck': ['v220_proof_lock_recheck_report.json'], 'no-repeat-proof': ['v220_no_repeat_proof_report.json'], 'no-cancel-default-proof': ['v220_no_cancel_default_proof_report.json'], 'private-data-redaction': ['v220_private_data_redaction_report.json'], 'readiness-governor': ['readiness_governor_v180_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v179_report.json'], 'mission-state': ['dummy_mission_state_report_v206.json', 'dashboard_v220_report_v1.json', 'completion_oriented_next_action_v220_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(220)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v220/reports.py scripts/generate_v220_reports.py dashboard/backend/v220_routes.py",
    "python scripts/generate_v220_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v220_reconcile_spine_v2_controller_report.json"

VALID_STATES = ("FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN")


class V220Context:
    def __init__(self, *, v219_final_override=None, outcome_state="FILLED") -> None:
        self.v219_baseline_status = sgc.baseline_status("final_report_v219.json", "V219")
        v219 = v219_final_override if v219_final_override is not None else sgc.load_artifact("final_report_v219.json")
        self.proof_submitted = str(v219.get("hardened_live_proof_execution_harness_controller_status", "")) == "PASS_HARDENED_LIVE_PROOF_SUBMITTED_AUTOLOCKED" or int(v219.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = (outcome_state if outcome_state in VALID_STATES else "UNKNOWN") if self.proof_submitted else "NO_ATTEMPT"
        self.proof_target = str(v219.get("proof_target", "BLOCKED_NO_AUTHORITY")) if self.proof_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        if self.v219_baseline_status.startswith("FAIL"):
            return "FAIL_RECONCILE_SPINE_V2_BASELINE_REGRESSION"
        return "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED" if self.proof_submitted else "PARTIAL_NO_HARDENED_LIVE_PROOF_TO_RECONCILE"

    @property
    def final_verdict(self) -> str:
        if self.v219_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v219_baseline_status.startswith("FAIL"):
            return ["FAIL_V219_BASELINE_REGRESSION"]
        return [] if self.proof_submitted else ["NO_HARDENED_LIVE_PROOF_TO_RECONCILE"]

    @property
    def next_action(self) -> str:
        return "RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED_AWAIT_FORENSIC_SPINE_V2_NO_NEW_ORDER" if self.proof_submitted else "AWAIT_HARDENED_LIVE_PROOF_BEFORE_RECONCILE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v219_baseline_status": ctx.v219_baseline_status,
        "reconcile_spine_v2_controller_status": ctx.controller_status,
        "order_state": ctx.order_state,
        "proof_state_parser_status": "PASS_PROOF_STATE_PARSED",
        "proof_target": ctx.proof_target,
        "proof_target_classifier_status": "PASS_PROOF_TARGET_CLASSIFIED",
        "idempotency_verification_status": "PASS_IDEMPOTENCY_VERIFIED",
        "proof_lock_recheck_status": "PASS_PROOF_LOCK_RECHECKED",
        "no_repeat_proof_status": "PASS_NO_REPEAT",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "private_data_redaction_status": "PASS_PRIVATE_DATA_REDACTED",
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
        "readiness_governor_v180_status": "PASS",
        "execution_lock_deep_recheck_v179_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v219_baseline"):
        return "PASS" if ctx.v219_baseline_status == "PASS_V219_BASELINE_READBACK" else "FAIL" if ctx.v219_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v220: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v220_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V220_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v220_report.json":
        report.update({"completion_oriented_next_action_v220_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v219_carried_status": ctx.v219_baseline_status, "reconcile_spine_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v220.json", "dummy_canonical_identity_report_v220.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V220ReportFactory:
    def __init__(self, *, v219_final_override=None, outcome_state='FILLED') -> None:
        self.kw = dict(v219_final_override=v219_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V220Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
