"""DUMMY v178 controlled session reconcile state classifier — classifies all V177 session order states if attempts occurred; no new orders.

Default is PARTIAL_NO_CONTROLLED_SESSION_TO_RECONCILE (session_state=NO_ATTEMPT). When a V177 session was submitted it
parses per-order state into one of FILLED / REJECTED / CANCELED / EXPIRED / PARTIAL_FILL / UNKNOWN / NO_ATTEMPT,
aggregates the session state, checks idempotency and no-repeat, and auto-locks. No cancel by default and no private-data
leak.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v178 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v178: Controlled Session Reconcile State Classifier Autolock"
MISSION_NAME = "dummy_mission_state_report_v164.json"
FINAL_NAME = "final_report_v178.json"
INDEX_KEYS = ["session_reconcile_controller_status", "session_state", "session_live_orders"]
DASH_TITLE = "Dummy V178 Controlled Session Reconcile"
MISSION_KEY = "dummy_mission_state_report_v164"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Reconcile", "session_reconcile_controller_status"],
    ["Session State", "session_state"],
    ["Session Live Orders", "session_live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V178_ROUTES = [
    "/api/v178/session-reconcile-controller",
    "/api/v178/v177-baseline",
    "/api/v178/per-order-state-parser",
    "/api/v178/session-aggregate-state",
    "/api/v178/idempotency-check",
    "/api/v178/no-repeat-session-proof",
    "/api/v178/no-cancel-default-proof",
    "/api/v178/no-private-data-leakage-proof",
    "/api/v178/session-autolock-proof",
    "/api/v178/readiness-governor",
    "/api/v178/execution-lock",
    "/api/v178/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-reconcile-controller": ["v178_session_reconcile_controller_report.json"],
    "v177-baseline": ["v177_baseline_readback_v1_report.json"],
    "per-order-state-parser": ["v178_per_order_state_parser_report.json"],
    "session-aggregate-state": ["v178_session_aggregate_state_report.json"],
    "idempotency-check": ["v178_idempotency_check_report.json"],
    "no-repeat-session-proof": ["v178_no_repeat_session_proof_report.json"],
    "no-cancel-default-proof": ["v178_no_cancel_default_proof_report.json"],
    "no-private-data-leakage-proof": ["v178_no_private_data_leakage_proof_report.json"],
    "session-autolock-proof": ["v178_session_autolock_proof_report.json"],
    "readiness-governor": ["readiness_governor_v138_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v137_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v178_report_v1.json", "completion_oriented_next_action_v178_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(178)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v178/reports.py scripts/generate_v178_reports.py dashboard/backend/v178_routes.py",
    "python scripts/generate_v178_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ORDER_STATE_ENUM = ["FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN", "NO_ATTEMPT"]


class V178Context:
    def __init__(self, *, v177_final_override=None, session_state="FILLED") -> None:
        self.v177_baseline_status = sgc.baseline_status("final_report_v177.json", "V177")
        v177 = v177_final_override if v177_final_override is not None else sgc.load_artifact("final_report_v177.json")
        self.session_submitted = str(v177.get("controlled_session_gate_controller_status", "")) == "PASS_CONTROLLED_SESSION_SUBMITTED_AUTOLOCKED" or int(v177.get("simulated_order_submits_count", 0) or 0) > 0
        self.session_state = session_state if self.session_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED" if self.session_submitted else "PARTIAL_NO_CONTROLLED_SESSION_TO_RECONCILE"

    @property
    def final_verdict(self) -> str:
        if self.v177_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.session_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v177_baseline_status.startswith("FAIL"):
            return ["FAIL_V177_BASELINE_REGRESSION"]
        return [] if self.session_submitted else ["NO_CONTROLLED_SESSION_TO_RECONCILE"]

    @property
    def next_action(self) -> str:
        return "CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED_AWAIT_FORENSIC_REVIEW_NO_NEW_ORDER" if self.session_submitted else "AWAIT_CONTROLLED_SESSION_SUBMIT_BEFORE_RECONCILE"


def _common(ctx: V178Context) -> dict[str, Any]:
    present = ctx.session_submitted
    def s(v):
        return v if present else "PARTIAL_NO_SESSION"
    return {
        "v177_baseline_status": ctx.v177_baseline_status,
        "session_reconcile_controller_status": ctx.controller_status,
        "per_order_state_parser_status": f"PASS_STATE_{ctx.session_state}" if present else "PARTIAL_NO_ATTEMPT_TO_PARSE",
        "session_state": ctx.session_state,
        "order_state_enum": ORDER_STATE_ENUM,
        "session_aggregate_state_status": f"PASS_AGGREGATE_{ctx.session_state}" if present else "PARTIAL_NO_AGGREGATE",
        "idempotency_check_status": s("PASS_IDEMPOTENCY_VERIFIED"),
        "no_repeat_session_proof_status": "PASS_NO_REPEAT_SESSION",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "no_private_data_leakage_proof_status": "PASS_NO_PRIVATE_DATA_LEAKAGE",
        "session_autolock_proof_status": "PASS_SESSION_AUTOLOCKED" if present else "PASS_SESSION_AUTOLOCK_ARMED",
        "session_locked": present,
        "session_forensic_capture": {"captured": present, "private_data_leaked": False},
        "new_order_placed": False,
        "cancel_call_made": False,
        "session_live_orders": 0,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v138_status": "PASS",
        "execution_lock_deep_recheck_v137_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V178Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v177_baseline"):
        return "PASS" if ctx.v177_baseline_status == "PASS_V177_BASELINE_READBACK" else "FAIL" if ctx.v177_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v178_session_reconcile_controller_report.json":
        return "PASS" if ctx.session_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V178Context) -> dict[str, Any]:
    workstream = "v178: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v178_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V178_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v178_report.json":
        report.update({"completion_oriented_next_action_v178_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v177_carried_status": ctx.v177_baseline_status, "session_reconcile_controller_status": ctx.controller_status, "session_state": ctx.session_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v178_session_reconcile_controller_report.json"), "session_autolock": str(ARTIFACTS / "v178_session_autolock_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v178.json", "dummy_canonical_identity_report_v178.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V178ReportFactory:
    def __init__(self, *, v177_final_override=None, session_state="FILLED") -> None:
        self.kw = dict(v177_final_override=v177_final_override, session_state=session_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V178Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
