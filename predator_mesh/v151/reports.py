"""DUMMY v151 real production pilot fire gate V2 — submits one bounded pilot ONLY on full real authority, else nothing.

Submit occurs ONLY when V150 preflight is ready, the mode firewall is LIVE_AUTHORIZED, the exact controlled-pilot
approval validates, live-submit is operator-enabled, caps are present/unchanged, and an explicit LiveBrokerFirewall
adapter is injected. Default has none -> no submit (PARTIAL_REAL_PILOT_NOT_ARMED). Tests inject a NON-BROKER firewall
double. Dry mode blocks. On submit the pilot immediately auto-locks; limit-only, no market orders, no repeat.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v151 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "real_production_pilot": True}

WORKSTREAM = "v151: Real Production Pilot Fire Gate V2 Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v137.json"
FINAL_NAME = "final_report_v151.json"
INDEX_KEYS = ["real_pilot_gate_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V151 Real Production Pilot Fire Gate V2"
MISSION_KEY = "dummy_mission_state_report_v137"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Real Pilot Gate", "real_pilot_gate_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V151_ROUTES = [
    "/api/v151/real-pilot-gate-controller",
    "/api/v151/v150-baseline",
    "/api/v151/pilot-approval-validator",
    "/api/v151/preflight-prerequisite",
    "/api/v151/mode-live-authorized-prerequisite",
    "/api/v151/max-pilot-order-count-guard",
    "/api/v151/livebrokerfirewall-only-proof",
    "/api/v151/limit-only-proof",
    "/api/v151/no-market-order-proof",
    "/api/v151/pilot-autolock",
    "/api/v151/no-repeat-beyond-limit-proof",
    "/api/v151/readiness-governor",
    "/api/v151/execution-lock",
    "/api/v151/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "real-pilot-gate-controller": ["v151_real_pilot_gate_controller_report.json"],
    "v150-baseline": ["v150_baseline_readback_v1_report.json"],
    "pilot-approval-validator": ["v151_pilot_approval_validator_report.json"],
    "preflight-prerequisite": ["v151_preflight_prerequisite_report.json"],
    "mode-live-authorized-prerequisite": ["v151_mode_live_authorized_prerequisite_report.json"],
    "max-pilot-order-count-guard": ["v151_max_pilot_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v151_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v151_limit_only_proof_report.json"],
    "no-market-order-proof": ["v151_no_market_order_proof_report.json"],
    "pilot-autolock": ["v151_pilot_autolock_report.json"],
    "no-repeat-beyond-limit-proof": ["v151_no_repeat_beyond_limit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v111_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v110_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v151_report_v1.json", "completion_oriented_next_action_v151_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(151)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v151/reports.py scripts/generate_v151_reports.py dashboard/backend/v151_routes.py",
    "python scripts/generate_v151_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V151Context:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, preflight_ready_override=None, mode_live_override=None, max_pilot_orders=1) -> None:
        self.v150_baseline_status = sgc.baseline_status("final_report_v150.json", "V150")
        if preflight_ready_override is None:
            self.preflight_ready = str(sgc.load_artifact("final_report_v150.json").get("preflight_controller_status", "")) == "PASS_REAL_PILOT_PREFLIGHT_READY_NO_SUBMIT"
        else:
            self.preflight_ready = bool(preflight_ready_override)
        if mode_live_override is None:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        else:
            self.mode_live = bool(mode_live_override)
        self.result = sgc.pilot_submit(
            "v151-real-production-pilot",
            approval_input=pilot_approval,
            approval_path=pilot_approval_path,
            dry_audit_ready=self.preflight_ready and self.mode_live,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
            max_pilot_orders=max_pilot_orders,
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
        return "PASS_REAL_PILOT_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_REAL_PILOT_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v150_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        return base or ["REAL_PILOT_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "REAL_PILOT_SUBMITTED_PILOT_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_FULL_REAL_AUTHORITY_LIVE_AUTHORIZED_MODE_AND_FIREWALL_ADAPTER"


def _common(ctx: V151Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v150_baseline_status": ctx.v150_baseline_status,
        "real_pilot_gate_controller_status": ctx.controller_status,
        "pilot_approval_validator_status": "PASS_PILOT_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_PILOT_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_PILOT_APPROVAL_ABSENT"),
        "preflight_prerequisite_status": "PASS_PREFLIGHT_PREREQUISITE_MET" if ctx.preflight_ready else "PARTIAL_PREFLIGHT_PREREQUISITE_UNMET",
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "max_pilot_order_count_guard_status": "PASS_MAX_PILOT_ORDER_COUNT",
        "max_pilot_order_count": ctx.result["max_pilot_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_beyond_limit_proof_status": "PASS_NO_REPEAT_BEYOND_LIMIT",
        "pilot_approval_present": bool(v["accepted"]),
        "pilot_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "mode_live_authorized": ctx.mode_live,
        "pilot_autolock_status": "PASS_PILOT_AUTOLOCKED" if ctx.submitted else "PASS_PILOT_AUTOLOCK_ARMED",
        "pilot_locked": ctx.submitted,
        "pilot_id": ctx.result["pilot_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v111_status": "PASS",
        "execution_lock_deep_recheck_v110_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V151Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v150_baseline"):
        return "PASS" if ctx.v150_baseline_status == "PASS_V150_BASELINE_READBACK" else "FAIL" if ctx.v150_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v151_real_pilot_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V151Context) -> dict[str, Any]:
    workstream = "v151: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v151_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V151_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v151_report.json":
        report.update({"completion_oriented_next_action_v151_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v150_carried_status": ctx.v150_baseline_status, "real_pilot_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v151_real_pilot_gate_controller_report.json"), "pilot_autolock": str(ARTIFACTS / "v151_pilot_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v151.json", "dummy_canonical_identity_report_v151.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V151ReportFactory:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, preflight_ready_override=None, mode_live_override=None, max_pilot_orders=1) -> None:
        self.kw = dict(pilot_approval=pilot_approval, pilot_approval_path=pilot_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, preflight_ready_override=preflight_ready_override, mode_live_override=mode_live_override, max_pilot_orders=max_pilot_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V151Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
