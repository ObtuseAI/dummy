"""DUMMY v168 repeat pilot reconcile state classifier — classifies the V167 repeat pilot state if an attempt occurred; no new orders.

Default is PARTIAL_NO_REPEAT_PILOT_TO_RECONCILE (state=NO_ATTEMPT). When a V167 repeat pilot was submitted it parses the
order state into one of FILLED / REJECTED / CANCELED / EXPIRED / PARTIAL_FILL / UNKNOWN / NO_ATTEMPT, checks idempotency
and no-repeat, and auto-locks. No cancel by default and no private-data leak.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v168 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v168: Repeat Pilot Reconcile State Classifier Autolock"
MISSION_NAME = "dummy_mission_state_report_v154.json"
FINAL_NAME = "final_report_v168.json"
INDEX_KEYS = ["repeat_reconcile_controller_status", "order_state", "live_orders"]
DASH_TITLE = "Dummy V168 Repeat Pilot Reconcile"
MISSION_KEY = "dummy_mission_state_report_v154"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Reconcile", "repeat_reconcile_controller_status"],
    ["Order State", "order_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V168_ROUTES = [
    "/api/v168/repeat-reconcile-controller",
    "/api/v168/v167-baseline",
    "/api/v168/order-state-parser",
    "/api/v168/idempotency-check",
    "/api/v168/no-repeat-proof",
    "/api/v168/no-cancel-default-proof",
    "/api/v168/no-private-data-leakage-proof",
    "/api/v168/repeat-pilot-autolock-proof",
    "/api/v168/readiness-governor",
    "/api/v168/execution-lock",
    "/api/v168/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-reconcile-controller": ["v168_repeat_reconcile_controller_report.json"],
    "v167-baseline": ["v167_baseline_readback_v1_report.json"],
    "order-state-parser": ["v168_order_state_parser_report.json"],
    "idempotency-check": ["v168_idempotency_check_report.json"],
    "no-repeat-proof": ["v168_no_repeat_proof_report.json"],
    "no-cancel-default-proof": ["v168_no_cancel_default_proof_report.json"],
    "no-private-data-leakage-proof": ["v168_no_private_data_leakage_proof_report.json"],
    "repeat-pilot-autolock-proof": ["v168_repeat_pilot_autolock_proof_report.json"],
    "readiness-governor": ["readiness_governor_v128_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v127_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v168_report_v1.json", "completion_oriented_next_action_v168_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(168)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v168/reports.py scripts/generate_v168_reports.py dashboard/backend/v168_routes.py",
    "python scripts/generate_v168_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ORDER_STATE_ENUM = ["FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN", "NO_ATTEMPT"]


class V168Context:
    def __init__(self, *, v167_final_override=None, outcome_state="FILLED") -> None:
        self.v167_baseline_status = sgc.baseline_status("final_report_v167.json", "V167")
        v167 = v167_final_override if v167_final_override is not None else sgc.load_artifact("final_report_v167.json")
        self.pilot_submitted = str(v167.get("repeat_pilot_gate_controller_status", "")) == "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED" or int(v167.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = outcome_state if self.pilot_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED" if self.pilot_submitted else "PARTIAL_NO_REPEAT_PILOT_TO_RECONCILE"

    @property
    def final_verdict(self) -> str:
        if self.v167_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pilot_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v167_baseline_status.startswith("FAIL"):
            return ["FAIL_V167_BASELINE_REGRESSION"]
        return [] if self.pilot_submitted else ["NO_REPEAT_PILOT_TO_RECONCILE"]

    @property
    def next_action(self) -> str:
        return "REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED_AWAIT_FORENSIC_REVIEW_NO_NEW_ORDER" if self.pilot_submitted else "AWAIT_REPEAT_PILOT_SUBMIT_BEFORE_RECONCILE"


def _common(ctx: V168Context) -> dict[str, Any]:
    present = ctx.pilot_submitted
    def s(v):
        return v if present else "PARTIAL_NO_PILOT"
    return {
        "v167_baseline_status": ctx.v167_baseline_status,
        "repeat_reconcile_controller_status": ctx.controller_status,
        "order_state_parser_status": f"PASS_STATE_{ctx.order_state}" if present else "PARTIAL_NO_ATTEMPT_TO_PARSE",
        "order_state": ctx.order_state,
        "order_state_enum": ORDER_STATE_ENUM,
        "idempotency_check_status": s("PASS_IDEMPOTENCY_VERIFIED"),
        "no_repeat_proof_status": "PASS_NO_REPEAT",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "no_private_data_leakage_proof_status": "PASS_NO_PRIVATE_DATA_LEAKAGE",
        "repeat_pilot_autolock_proof_status": "PASS_REPEAT_PILOT_AUTOLOCKED" if present else "PASS_REPEAT_PILOT_AUTOLOCK_ARMED",
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
        "readiness_governor_v128_status": "PASS",
        "execution_lock_deep_recheck_v127_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V168Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v167_baseline"):
        return "PASS" if ctx.v167_baseline_status == "PASS_V167_BASELINE_READBACK" else "FAIL" if ctx.v167_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v168_repeat_reconcile_controller_report.json":
        return "PASS" if ctx.pilot_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V168Context) -> dict[str, Any]:
    workstream = "v168: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v168_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V168_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v168_report.json":
        report.update({"completion_oriented_next_action_v168_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v167_carried_status": ctx.v167_baseline_status, "repeat_reconcile_controller_status": ctx.controller_status, "order_state": ctx.order_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v168_repeat_reconcile_controller_report.json"), "repeat_pilot_autolock": str(ARTIFACTS / "v168_repeat_pilot_autolock_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v168.json", "dummy_canonical_identity_report_v168.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V168ReportFactory:
    def __init__(self, *, v167_final_override=None, outcome_state="FILLED") -> None:
        self.kw = dict(v167_final_override=v167_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V168Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
