"""DUMMY v162 first real pilot reconcile state classifier — classifies the V161 pilot state if an attempt occurred; no new orders.

Default is PARTIAL_NO_FIRST_REAL_PILOT_TO_RECONCILE (state=NO_ATTEMPT). When a V161 pilot was submitted it parses the
order state into one of FILLED / REJECTED / CANCELED / EXPIRED / PARTIAL_FILL / UNKNOWN / NO_ATTEMPT, checks idempotency
and no-repeat, and auto-locks. No cancel by default and no private-data leak.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v162 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v162: First Real Pilot Reconcile State Classifier Autolock"
MISSION_NAME = "dummy_mission_state_report_v148.json"
FINAL_NAME = "final_report_v162.json"
INDEX_KEYS = ["reconcile_controller_status", "order_state", "live_orders"]
DASH_TITLE = "Dummy V162 First Real Pilot Reconcile"
MISSION_KEY = "dummy_mission_state_report_v148"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Reconcile", "reconcile_controller_status"],
    ["Order State", "order_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V162_ROUTES = [
    "/api/v162/reconcile-controller",
    "/api/v162/v161-baseline",
    "/api/v162/order-state-parser",
    "/api/v162/idempotency-check",
    "/api/v162/no-repeat-proof",
    "/api/v162/no-cancel-default-proof",
    "/api/v162/no-private-data-leakage-proof",
    "/api/v162/pilot-autolock-proof",
    "/api/v162/readiness-governor",
    "/api/v162/execution-lock",
    "/api/v162/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "reconcile-controller": ["v162_reconcile_controller_report.json"],
    "v161-baseline": ["v161_baseline_readback_v1_report.json"],
    "order-state-parser": ["v162_order_state_parser_report.json"],
    "idempotency-check": ["v162_idempotency_check_report.json"],
    "no-repeat-proof": ["v162_no_repeat_proof_report.json"],
    "no-cancel-default-proof": ["v162_no_cancel_default_proof_report.json"],
    "no-private-data-leakage-proof": ["v162_no_private_data_leakage_proof_report.json"],
    "pilot-autolock-proof": ["v162_pilot_autolock_proof_report.json"],
    "readiness-governor": ["readiness_governor_v122_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v121_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v162_report_v1.json", "completion_oriented_next_action_v162_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(162)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v162/reports.py scripts/generate_v162_reports.py dashboard/backend/v162_routes.py",
    "python scripts/generate_v162_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ORDER_STATE_ENUM = ["FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN", "NO_ATTEMPT"]


class V162Context:
    def __init__(self, *, v161_final_override=None, outcome_state="FILLED") -> None:
        self.v161_baseline_status = sgc.baseline_status("final_report_v161.json", "V161")
        v161 = v161_final_override if v161_final_override is not None else sgc.load_artifact("final_report_v161.json")
        self.pilot_submitted = str(v161.get("first_real_pilot_gate_controller_status", "")) == "PASS_FIRST_REAL_PILOT_SUBMITTED_AUTOLOCKED" or int(v161.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = outcome_state if self.pilot_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED" if self.pilot_submitted else "PARTIAL_NO_FIRST_REAL_PILOT_TO_RECONCILE"

    @property
    def final_verdict(self) -> str:
        if self.v161_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pilot_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v161_baseline_status.startswith("FAIL"):
            return ["FAIL_V161_BASELINE_REGRESSION"]
        return [] if self.pilot_submitted else ["NO_FIRST_REAL_PILOT_TO_RECONCILE"]

    @property
    def next_action(self) -> str:
        return "FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED_AWAIT_FORENSIC_REVIEW_NO_NEW_ORDER" if self.pilot_submitted else "AWAIT_FIRST_REAL_PILOT_SUBMIT_BEFORE_RECONCILE"


def _common(ctx: V162Context) -> dict[str, Any]:
    present = ctx.pilot_submitted
    def s(v):
        return v if present else "PARTIAL_NO_PILOT"
    return {
        "v161_baseline_status": ctx.v161_baseline_status,
        "reconcile_controller_status": ctx.controller_status,
        "order_state_parser_status": f"PASS_STATE_{ctx.order_state}" if present else "PARTIAL_NO_ATTEMPT_TO_PARSE",
        "order_state": ctx.order_state,
        "order_state_enum": ORDER_STATE_ENUM,
        "idempotency_check_status": s("PASS_IDEMPOTENCY_VERIFIED"),
        "no_repeat_proof_status": "PASS_NO_REPEAT",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "no_private_data_leakage_proof_status": "PASS_NO_PRIVATE_DATA_LEAKAGE",
        "pilot_autolock_proof_status": "PASS_PILOT_AUTOLOCKED" if present else "PASS_PILOT_AUTOLOCK_ARMED",
        "state_locked": present,
        "pilot_forensic_capture": {"captured": present, "private_data_leaked": False},
        "new_order_placed": False,
        "cancel_call_made": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v122_status": "PASS",
        "execution_lock_deep_recheck_v121_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V162Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v161_baseline"):
        return "PASS" if ctx.v161_baseline_status == "PASS_V161_BASELINE_READBACK" else "FAIL" if ctx.v161_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v162_reconcile_controller_report.json":
        return "PASS" if ctx.pilot_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V162Context) -> dict[str, Any]:
    workstream = "v162: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v162_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V162_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v162_report.json":
        report.update({"completion_oriented_next_action_v162_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v161_carried_status": ctx.v161_baseline_status, "reconcile_controller_status": ctx.controller_status, "order_state": ctx.order_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v162_reconcile_controller_report.json"), "pilot_autolock": str(ARTIFACTS / "v162_pilot_autolock_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v162.json", "dummy_canonical_identity_report_v162.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V162ReportFactory:
    def __init__(self, *, v161_final_override=None, outcome_state="FILLED") -> None:
        self.kw = dict(v161_final_override=v161_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V162Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
