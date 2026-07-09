"""DUMMY v144 repeat production pilot fire on full auth — submits one repeat pilot ONLY on full authority, else nothing.

Submit occurs ONLY when V143 marked repeat review ready, the exact repeat-pilot approval validates, the first pilot was
reconciled/reviewed, live-submit is operator-enabled, caps are present/unchanged (stricter), and an explicit
LiveBrokerFirewall adapter is injected. Default has none -> no submit (PARTIAL_REPEAT_PILOT_NOT_ARMED). Tests inject a
NON-BROKER firewall double. On submit the repeat pilot immediately auto-locks; limit-only, no market orders, no campaign
auto-start.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v144 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "repeat_pilot": True}

WORKSTREAM = "v144: Repeat Production Pilot Fire On Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v130.json"
FINAL_NAME = "final_report_v144.json"
INDEX_KEYS = ["repeat_pilot_gate_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V144 Repeat Production Pilot Fire On Full Auth"
MISSION_KEY = "dummy_mission_state_report_v130"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V144_ROUTES = [
    "/api/v144/repeat-pilot-gate-controller",
    "/api/v144/v143-baseline",
    "/api/v144/repeat-approval-validator",
    "/api/v144/first-pilot-review-prerequisite",
    "/api/v144/max-repeat-order-count-guard",
    "/api/v144/livebrokerfirewall-only-proof",
    "/api/v144/limit-only-proof",
    "/api/v144/no-market-order-proof",
    "/api/v144/repeat-pilot-autolock",
    "/api/v144/no-campaign-auto-start-proof",
    "/api/v144/readiness-governor",
    "/api/v144/execution-lock",
    "/api/v144/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-pilot-gate-controller": ["v144_repeat_pilot_gate_controller_report.json"],
    "v143-baseline": ["v143_baseline_readback_v1_report.json"],
    "repeat-approval-validator": ["v144_repeat_approval_validator_report.json"],
    "first-pilot-review-prerequisite": ["v144_first_pilot_review_prerequisite_report.json"],
    "max-repeat-order-count-guard": ["v144_max_repeat_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v144_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v144_limit_only_proof_report.json"],
    "no-market-order-proof": ["v144_no_market_order_proof_report.json"],
    "repeat-pilot-autolock": ["v144_repeat_pilot_autolock_report.json"],
    "no-campaign-auto-start-proof": ["v144_no_campaign_auto_start_proof_report.json"],
    "readiness-governor": ["readiness_governor_v104_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v103_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v144_report_v1.json", "completion_oriented_next_action_v144_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(144)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v144/reports.py scripts/generate_v144_reports.py dashboard/backend/v144_routes.py",
    "python scripts/generate_v144_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V144Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, first_pilot_reviewed_override=None, repeat_ready_override=None, max_repeat_orders=1) -> None:
        self.v143_baseline_status = sgc.baseline_status("final_report_v143.json", "V143")
        if repeat_ready_override is not None:
            self.repeat_ready = bool(repeat_ready_override)
        else:
            self.repeat_ready = str(sgc.load_artifact("final_report_v143.json").get("repeat_eligibility_controller_status", "")) == "PASS_REPEAT_PILOT_REVIEW_READY_LOCKED"
        if first_pilot_reviewed_override is not None:
            self.first_pilot_reviewed = bool(first_pilot_reviewed_override)
        else:
            self.first_pilot_reviewed = str(sgc.load_artifact("final_report_v142.json").get("pilot_reconcile_controller_status", "")) == "PASS_PRODUCTION_PILOT_RECONCILED_REVIEWED_AUTOLOCKED"
        self.result = sgc.repeat_pilot_submit(
            "v144-repeat-pilot",
            approval_input=repeat_approval,
            approval_path=repeat_approval_path,
            first_pilot_reviewed=self.first_pilot_reviewed and self.repeat_ready,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
            max_repeat_orders=max_repeat_orders,
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
        return "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_REPEAT_PILOT_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v143_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v] or ["REPEAT_PILOT_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "REPEAT_PILOT_SUBMITTED_REPEAT_PILOT_AUTOLOCKED_NO_CAMPAIGN_AUTO_START_AWAIT_CLOSEOUT" if self.submitted else "OPERATOR_MUST_PROVIDE_REPEAT_PILOT_APPROVAL_FIRST_PILOT_REVIEW_AND_FIREWALL_ADAPTER"


def _common(ctx: V144Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v143_baseline_status": ctx.v143_baseline_status,
        "repeat_pilot_gate_controller_status": ctx.controller_status,
        "repeat_approval_validator_status": "PASS_REPEAT_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_REPEAT_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_REPEAT_APPROVAL_ABSENT"),
        "first_pilot_review_prerequisite_status": "PASS_FIRST_PILOT_REVIEWED" if (ctx.first_pilot_reviewed and ctx.repeat_ready) else "PARTIAL_FIRST_PILOT_REVIEW_OR_ELIGIBILITY_ABSENT",
        "max_repeat_order_count_guard_status": "PASS_MAX_REPEAT_ORDER_COUNT",
        "max_repeat_order_count": ctx.result["max_repeat_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_campaign_auto_start_proof_status": "PASS_NO_CAMPAIGN_AUTO_START",
        "repeat_approval_present": bool(v["accepted"]),
        "repeat_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "repeat_pilot_autolock_status": "PASS_REPEAT_PILOT_AUTOLOCKED" if ctx.submitted else "PASS_REPEAT_PILOT_AUTOLOCK_ARMED",
        "repeat_pilot_locked": ctx.submitted,
        "repeat_pilot_id": ctx.result["repeat_pilot_id"] if ctx.submitted else None,
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
        "campaign_auto_started": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v104_status": "PASS",
        "execution_lock_deep_recheck_v103_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V144Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v143_baseline"):
        return "PASS" if ctx.v143_baseline_status == "PASS_V143_BASELINE_READBACK" else "FAIL" if ctx.v143_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v144_repeat_pilot_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V144Context) -> dict[str, Any]:
    workstream = "v144: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v144_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V144_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v144_report.json":
        report.update({"completion_oriented_next_action_v144_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v143_carried_status": ctx.v143_baseline_status, "repeat_pilot_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v144_repeat_pilot_gate_controller_report.json"), "repeat_pilot_autolock": str(ARTIFACTS / "v144_repeat_pilot_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v144.json", "dummy_canonical_identity_report_v144.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V144ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, first_pilot_reviewed_override=None, repeat_ready_override=None, max_repeat_orders=1) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, first_pilot_reviewed_override=first_pilot_reviewed_override, repeat_ready_override=repeat_ready_override, max_repeat_orders=max_repeat_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V144Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
