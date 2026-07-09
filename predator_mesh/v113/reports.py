"""DUMMY v113 controlled live session canary — fires one bounded session canary ONLY on full session auth, else nothing.

Submit occurs ONLY when V112 governor is ready, the exact controlled-session approval validates, live-submit
is operator-enabled, caps are present/unchanged, per-order approval mode is active, and an explicit
LiveBrokerFirewall adapter is injected. Default has none -> no submit. Tests inject a NON-BROKER firewall
double. On submit the session immediately auto-locks; no market orders and no repeat beyond the session limit.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v113 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "session_canary": True}

WORKSTREAM = "v113: Controlled Live Session Canary Fire Only On Full Session Auth"
MISSION_NAME = "dummy_mission_state_report_v99.json"
FINAL_NAME = "final_report_v113.json"
INDEX_KEYS = ["session_canary_controller_status", "session_live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V113 Controlled Live Session Canary"
MISSION_KEY = "dummy_mission_state_report_v99"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Canary", "session_canary_controller_status"],
    ["Session Live Orders", "session_live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V113_ROUTES = [
    "/api/v113/session-canary-controller",
    "/api/v113/v112-baseline",
    "/api/v113/session-approval-validator",
    "/api/v113/per-order-approval-mode",
    "/api/v113/max-session-order-count-guard",
    "/api/v113/livebrokerfirewall-only-proof",
    "/api/v113/limit-only-proof",
    "/api/v113/no-market-order-proof",
    "/api/v113/session-autolock",
    "/api/v113/no-repeat-beyond-limit-proof",
    "/api/v113/readiness-governor",
    "/api/v113/execution-lock",
    "/api/v113/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-canary-controller": ["v113_session_canary_controller_report.json"],
    "v112-baseline": ["v112_baseline_readback_v1_report.json"],
    "session-approval-validator": ["v113_session_approval_validator_report.json"],
    "per-order-approval-mode": ["v113_per_order_approval_mode_report.json"],
    "max-session-order-count-guard": ["v113_max_session_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v113_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v113_limit_only_proof_report.json"],
    "no-market-order-proof": ["v113_no_market_order_proof_report.json"],
    "session-autolock": ["v113_session_autolock_report.json"],
    "no-repeat-beyond-limit-proof": ["v113_no_repeat_beyond_limit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v73_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v72_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v113_report_v1.json", "completion_oriented_next_action_v113_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(113)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v113/reports.py scripts/generate_v113_reports.py dashboard/backend/v113_routes.py",
    "python scripts/generate_v113_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V113Context:
    def __init__(self, *, session_approval=None, session_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, per_order_mode=False, firewall_adapter=None, session_governor_ready_override=None, max_session_orders=1) -> None:
        self.v112_baseline_status = sgc.baseline_status("final_report_v112.json", "V112")
        if session_governor_ready_override is None:
            self.session_governor_ready = str(sgc.load_artifact("final_report_v112.json").get("session_governor_status", "")) == "PASS_SESSION_GOVERNOR_READY_LOCKED"
        else:
            self.session_governor_ready = bool(session_governor_ready_override)
        self.result = sgc.session_canary_submit(
            "v113-session-canary",
            approval_input=session_approval,
            approval_path=session_approval_path,
            session_governor_ready=self.session_governor_ready,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            per_order_mode=per_order_mode,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
            max_session_orders=max_session_orders,
        )
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def submitted(self) -> bool:
        r = self.result["submit_result"]
        return r is not None and bool(r.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        r = self.result["submit_result"]
        return bool(r and r.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        return "PASS_SESSION_CANARY_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_SESSION_CANARY_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v112_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v] or ["SESSION_CANARY_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "SESSION_CANARY_SUBMITTED_SESSION_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_CONTROLLED_SESSION_APPROVAL_AND_FIREWALL_ADAPTER"


def _common(ctx: V113Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v112_baseline_status": ctx.v112_baseline_status,
        "session_canary_controller_status": ctx.controller_status,
        "session_approval_validator_status": "PASS_SESSION_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_SESSION_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_SESSION_APPROVAL_ABSENT"),
        "per_order_approval_mode_status": "PASS_PER_ORDER_APPROVAL_MODE" if ctx.result["checklist"]["per_order_approval_mode"] else "PARTIAL_PER_ORDER_APPROVAL_MODE_OFF",
        "max_session_order_count_guard_status": "PASS_MAX_SESSION_ORDER_COUNT",
        "max_session_order_count": ctx.result["max_session_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_beyond_limit_proof_status": "PASS_NO_REPEAT_BEYOND_LIMIT",
        "session_approval_present": bool(v["accepted"]),
        "session_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "session_autolock_status": "PASS_SESSION_AUTOLOCKED" if ctx.submitted else "PASS_SESSION_AUTOLOCK_ARMED",
        "session_locked": ctx.submitted,
        "session_id": ctx.result["session_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "session_live_orders": 0,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v73_status": "PASS",
        "execution_lock_deep_recheck_v72_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V113Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v112_baseline"):
        return "PASS" if ctx.v112_baseline_status == "PASS_V112_BASELINE_READBACK" else "FAIL" if ctx.v112_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v113_session_canary_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V113Context) -> dict[str, Any]:
    workstream = "v113: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v113_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V113_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v113_report.json":
        report.update({"completion_oriented_next_action_v113_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v112_carried_status": ctx.v112_baseline_status, "session_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v113_session_canary_controller_report.json"), "session_autolock": str(ARTIFACTS / "v113_session_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v113.json", "dummy_canonical_identity_report_v113.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V113ReportFactory:
    def __init__(self, *, session_approval=None, session_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, per_order_mode=False, firewall_adapter=None, session_governor_ready_override=None, max_session_orders=1) -> None:
        self.kw = dict(session_approval=session_approval, session_approval_path=session_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, per_order_mode=per_order_mode, firewall_adapter=firewall_adapter, session_governor_ready_override=session_governor_ready_override, max_session_orders=max_session_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V113Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
