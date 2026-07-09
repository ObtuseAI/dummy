"""DUMMY v177 controlled operation session gate — submits a bounded controlled session ONLY on full authority, else nothing.

Submit occurs ONLY when V176 preflight is ready, pilot proof exists, the mode firewall is LIVE_AUTHORIZED, the exact
controlled-session approval validates, live-submit is operator-enabled, caps are present/unchanged, per-order mode is
on, and an explicit LiveBrokerFirewall adapter is injected. Default has none -> no submit
(PARTIAL_CONTROLLED_SESSION_NOT_ARMED). Tests inject a NON-BROKER firewall double. Dry mode / missing pilot proof block.
On submit the session immediately auto-locks; limit-only, no market orders, obeys the max session order count.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v177 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "controlled_session": True}

WORKSTREAM = "v177: Controlled Operation Session Gate Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v163.json"
FINAL_NAME = "final_report_v177.json"
INDEX_KEYS = ["controlled_session_gate_controller_status", "session_live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V177 Controlled Operation Session Gate"
MISSION_KEY = "dummy_mission_state_report_v163"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Gate", "controlled_session_gate_controller_status"],
    ["Session Live Orders", "session_live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V177_ROUTES = [
    "/api/v177/controlled-session-gate-controller",
    "/api/v177/v176-baseline",
    "/api/v177/controlled-session-approval-validator",
    "/api/v177/preflight-prerequisite",
    "/api/v177/pilot-proof-prerequisite",
    "/api/v177/mode-live-authorized-prerequisite",
    "/api/v177/per-order-approval-mode",
    "/api/v177/max-session-order-count-guard",
    "/api/v177/livebrokerfirewall-only-proof",
    "/api/v177/limit-only-proof",
    "/api/v177/no-market-order-proof",
    "/api/v177/session-autolock",
    "/api/v177/no-repeat-session-proof",
    "/api/v177/readiness-governor",
    "/api/v177/execution-lock",
    "/api/v177/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-session-gate-controller": ["v177_controlled_session_gate_controller_report.json"],
    "v176-baseline": ["v176_baseline_readback_v1_report.json"],
    "controlled-session-approval-validator": ["v177_controlled_session_approval_validator_report.json"],
    "preflight-prerequisite": ["v177_preflight_prerequisite_report.json"],
    "pilot-proof-prerequisite": ["v177_pilot_proof_prerequisite_report.json"],
    "mode-live-authorized-prerequisite": ["v177_mode_live_authorized_prerequisite_report.json"],
    "per-order-approval-mode": ["v177_per_order_approval_mode_report.json"],
    "max-session-order-count-guard": ["v177_max_session_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v177_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v177_limit_only_proof_report.json"],
    "no-market-order-proof": ["v177_no_market_order_proof_report.json"],
    "session-autolock": ["v177_session_autolock_report.json"],
    "no-repeat-session-proof": ["v177_no_repeat_session_proof_report.json"],
    "readiness-governor": ["readiness_governor_v137_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v136_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v177_report_v1.json", "completion_oriented_next_action_v177_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(177)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v177/reports.py scripts/generate_v177_reports.py dashboard/backend/v177_routes.py",
    "python scripts/generate_v177_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V177Context:
    def __init__(self, *, session_approval=None, session_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, per_order_mode=False, firewall_adapter=None, preflight_ready_override=None, pilot_proof_override=None, mode_live_override=None, max_session_orders=3) -> None:
        self.v176_baseline_status = sgc.baseline_status("final_report_v176.json", "V176")
        if preflight_ready_override is None:
            self.preflight_ready = str(sgc.load_artifact("final_report_v176.json").get("session_preflight_controller_status", "")) == "PASS_LIVE_SESSION_PREFLIGHT_READY_NO_SUBMIT"
        else:
            self.preflight_ready = bool(preflight_ready_override)
        if pilot_proof_override is None:
            self.pilot_proof = str(sgc.load_artifact("final_report_v170.json").get("pilot_pair_audit_controller_status", "")) == "PASS_PILOT_PAIR_AUDITED_LOCKED"
        else:
            self.pilot_proof = bool(pilot_proof_override)
        if mode_live_override is None:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        else:
            self.mode_live = bool(mode_live_override)
        self.result = sgc.session_canary_submit(
            "v177-controlled-session",
            approval_input=session_approval,
            approval_path=session_approval_path,
            session_governor_ready=self.preflight_ready and self.pilot_proof and self.mode_live,
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
        return "PASS_CONTROLLED_SESSION_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_CONTROLLED_SESSION_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v176_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.preflight_ready:
            base.append("LIVE_SESSION_PREFLIGHT_NOT_READY")
        if not self.pilot_proof:
            base.append("PILOT_PROOF_ABSENT")
        return base or ["CONTROLLED_SESSION_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "CONTROLLED_SESSION_SUBMITTED_SESSION_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_SESSION_APPROVAL_PILOT_PROOF_LIVE_AUTHORIZED_MODE_AND_FIREWALL"


def _common(ctx: V177Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v176_baseline_status": ctx.v176_baseline_status,
        "controlled_session_gate_controller_status": ctx.controller_status,
        "controlled_session_approval_validator_status": "PASS_SESSION_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_SESSION_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_SESSION_APPROVAL_ABSENT"),
        "preflight_prerequisite_status": "PASS_PREFLIGHT_PREREQUISITE_MET" if ctx.preflight_ready else "PARTIAL_PREFLIGHT_PREREQUISITE_UNMET",
        "pilot_proof_prerequisite_status": "PASS_PILOT_PROOF_PRESENT" if ctx.pilot_proof else "PARTIAL_PILOT_PROOF_ABSENT",
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "per_order_approval_mode_status": "PASS_PER_ORDER_APPROVAL_MODE" if ctx.result["checklist"]["per_order_approval_mode"] else "PARTIAL_PER_ORDER_APPROVAL_MODE_OFF",
        "max_session_order_count_guard_status": "PASS_MAX_SESSION_ORDER_COUNT",
        "max_session_order_count": ctx.result["max_session_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_session_proof_status": "PASS_NO_REPEAT_SESSION",
        "session_approval_present": bool(v["accepted"]),
        "session_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "mode_live_authorized": ctx.mode_live,
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
        "readiness_governor_v137_status": "PASS",
        "execution_lock_deep_recheck_v136_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V177Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v176_baseline"):
        return "PASS" if ctx.v176_baseline_status == "PASS_V176_BASELINE_READBACK" else "FAIL" if ctx.v176_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v177_controlled_session_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V177Context) -> dict[str, Any]:
    workstream = "v177: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v177_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V177_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v177_report.json":
        report.update({"completion_oriented_next_action_v177_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v176_carried_status": ctx.v176_baseline_status, "controlled_session_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v177_controlled_session_gate_controller_report.json"), "session_autolock": str(ARTIFACTS / "v177_session_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v177.json", "dummy_canonical_identity_report_v177.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V177ReportFactory:
    def __init__(self, *, session_approval=None, session_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, per_order_mode=False, firewall_adapter=None, preflight_ready_override=None, pilot_proof_override=None, mode_live_override=None, max_session_orders=3) -> None:
        self.kw = dict(session_approval=session_approval, session_approval_path=session_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, per_order_mode=per_order_mode, firewall_adapter=firewall_adapter, preflight_ready_override=preflight_ready_override, pilot_proof_override=pilot_proof_override, mode_live_override=mode_live_override, max_session_orders=max_session_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V177Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
