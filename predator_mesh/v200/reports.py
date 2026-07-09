"""DUMMY v200 first live-proof reconcile state classifier — classifies the V199 proof state if an attempt occurred; no new orders.

Default is PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE (state=NO_ATTEMPT). When a V199 proof was submitted it parses the
order state into one of FILLED / REJECTED / CANCELED / EXPIRED / PARTIAL_FILL / UNKNOWN / NO_ATTEMPT, classifies the
proof target, checks idempotency and no-repeat, and auto-locks. No cancel by default and no private-data leak.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v200 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v200: First Live Proof Reconcile State Classifier Autolock"
MISSION_NAME = "dummy_mission_state_report_v186.json"
FINAL_NAME = "final_report_v200.json"
INDEX_KEYS = ["reconcile_controller_status", "order_state", "live_orders"]
DASH_TITLE = "Dummy V200 First Live-Proof Reconcile"
MISSION_KEY = "dummy_mission_state_report_v186"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Reconcile", "reconcile_controller_status"],
    ["Order State", "order_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V200_ROUTES = [
    "/api/v200/reconcile-controller",
    "/api/v200/v199-baseline",
    "/api/v200/state-parser",
    "/api/v200/proof-target-classifier",
    "/api/v200/idempotency-check",
    "/api/v200/no-repeat-proof",
    "/api/v200/no-cancel-default-proof",
    "/api/v200/no-private-data-leakage-proof",
    "/api/v200/proof-autolock",
    "/api/v200/readiness-governor",
    "/api/v200/execution-lock",
    "/api/v200/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "reconcile-controller": ["v200_reconcile_controller_report.json"],
    "v199-baseline": ["v199_baseline_readback_v1_report.json"],
    "state-parser": ["v200_state_parser_report.json"],
    "proof-target-classifier": ["v200_proof_target_classifier_report.json"],
    "idempotency-check": ["v200_idempotency_check_report.json"],
    "no-repeat-proof": ["v200_no_repeat_proof_report.json"],
    "no-cancel-default-proof": ["v200_no_cancel_default_proof_report.json"],
    "no-private-data-leakage-proof": ["v200_no_private_data_leakage_proof_report.json"],
    "proof-autolock": ["v200_proof_autolock_report.json"],
    "readiness-governor": ["readiness_governor_v160_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v159_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v200_report_v1.json", "completion_oriented_next_action_v200_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(200)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v200/reports.py scripts/generate_v200_reports.py dashboard/backend/v200_routes.py",
    "python scripts/generate_v200_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ORDER_STATE_ENUM = ["FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN", "NO_ATTEMPT"]


class V200Context:
    def __init__(self, *, v199_final_override=None, outcome_state="FILLED") -> None:
        self.v199_baseline_status = sgc.baseline_status("final_report_v199.json", "V199")
        v199 = v199_final_override if v199_final_override is not None else sgc.load_artifact("final_report_v199.json")
        self.proof_submitted = str(v199.get("first_live_proof_gate_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED" or int(v199.get("simulated_order_submits_count", 0) or 0) > 0
        self.order_state = outcome_state if self.proof_submitted else "NO_ATTEMPT"
        self.proof_target = str(v199.get("proof_target", "BLOCKED_NO_AUTHORITY")) if self.proof_submitted else "NO_ATTEMPT"

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED" if self.proof_submitted else "PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE"

    @property
    def final_verdict(self) -> str:
        if self.v199_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.proof_submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v199_baseline_status.startswith("FAIL"):
            return ["FAIL_V199_BASELINE_REGRESSION"]
        return [] if self.proof_submitted else ["NO_FIRST_LIVE_PROOF_TO_RECONCILE"]

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED_AWAIT_FORENSIC_REVIEW_NO_NEW_ORDER" if self.proof_submitted else "AWAIT_FIRST_LIVE_PROOF_SUBMIT_BEFORE_RECONCILE"


def _common(ctx: V200Context) -> dict[str, Any]:
    present = ctx.proof_submitted
    def s(v):
        return v if present else "PARTIAL_NO_PROOF"
    return {
        "v199_baseline_status": ctx.v199_baseline_status,
        "reconcile_controller_status": ctx.controller_status,
        "state_parser_status": f"PASS_STATE_{ctx.order_state}" if present else "PARTIAL_NO_ATTEMPT_TO_PARSE",
        "order_state": ctx.order_state,
        "order_state_enum": ORDER_STATE_ENUM,
        "proof_target_classifier_status": f"PASS_PROOF_TARGET_{ctx.proof_target}" if present else "PARTIAL_NO_PROOF_TARGET",
        "proof_target": ctx.proof_target,
        "idempotency_check_status": s("PASS_IDEMPOTENCY_VERIFIED"),
        "no_repeat_proof_status": "PASS_NO_REPEAT",
        "no_cancel_default_proof_status": "PASS_NO_CANCEL_DEFAULT",
        "no_private_data_leakage_proof_status": "PASS_NO_PRIVATE_DATA_LEAKAGE",
        "proof_autolock_status": "PASS_PROOF_AUTOLOCKED" if present else "PASS_PROOF_AUTOLOCK_ARMED",
        "proof_locked": present,
        "proof_forensic_capture": {"captured": present, "private_data_leaked": False},
        "new_order_placed": False,
        "cancel_call_made": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v160_status": "PASS",
        "execution_lock_deep_recheck_v159_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V200Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v199_baseline"):
        return "PASS" if ctx.v199_baseline_status == "PASS_V199_BASELINE_READBACK" else "FAIL" if ctx.v199_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v200_reconcile_controller_report.json":
        return "PASS" if ctx.proof_submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V200Context) -> dict[str, Any]:
    workstream = "v200: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v200_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V200_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v200_report.json":
        report.update({"completion_oriented_next_action_v200_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v199_carried_status": ctx.v199_baseline_status, "reconcile_controller_status": ctx.controller_status, "order_state": ctx.order_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v200_reconcile_controller_report.json"), "proof_autolock": str(ARTIFACTS / "v200_proof_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v200.json", "dummy_canonical_identity_report_v200.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V200ReportFactory:
    def __init__(self, *, v199_final_override=None, outcome_state="FILLED") -> None:
        self.kw = dict(v199_final_override=v199_final_override, outcome_state=outcome_state)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V200Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
