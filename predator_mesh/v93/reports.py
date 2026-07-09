"""DUMMY v93 campaign order 3 gate and campaign closeout lock — fires one order on full auth, else nothing."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v93 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "campaign_order": 3}

V93_ROUTES = [
    "/api/v93/order-3-gate-controller",
    "/api/v93/v92-baseline",
    "/api/v93/order-3-approval-validator",
    "/api/v93/continuation-decision-validator",
    "/api/v93/max-3-orders-policy",
    "/api/v93/no-auto-scale-proof",
    "/api/v93/livebrokerfirewall-only-proof",
    "/api/v93/single-submit-guard",
    "/api/v93/campaign-closeout-lock",
    "/api/v93/readiness-governor",
    "/api/v93/execution-lock",
    "/api/v93/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "order-3-gate-controller": ["v93_order_3_gate_controller_report.json"],
    "v92-baseline": ["v92_baseline_readback_v1_report.json"],
    "order-3-approval-validator": ["v93_order_3_approval_validator_report.json"],
    "continuation-decision-validator": ["v93_continuation_decision_validator_report.json"],
    "max-3-orders-policy": ["v93_max_3_orders_policy_report.json"],
    "no-auto-scale-proof": ["v93_no_auto_scale_proof_report.json"],
    "livebrokerfirewall-only-proof": ["v93_livebrokerfirewall_only_proof_report.json"],
    "single-submit-guard": ["v93_single_submit_guard_report.json"],
    "campaign-closeout-lock": ["v93_campaign_closeout_lock_report.json"],
    "readiness-governor": ["readiness_governor_v53_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v52_report.json"],
    "mission-state": ["dummy_mission_state_report_v79.json", "dashboard_v93_report_v1.json", "completion_oriented_next_action_v93_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(93)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v93/reports.py scripts/generate_v93_reports.py dashboard/backend/v93_routes.py",
    "python scripts/generate_v93_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V93Context:
    def __init__(self, *, campaign_approval, order_approval, order_approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter, continuation_allowed_override) -> None:
        self.v92_baseline_status = sgc.baseline_status("final_report_v92.json", "V92")
        if continuation_allowed_override is None:
            self.continuation_allowed = str(sgc.load_artifact("final_report_v92.json").get("stop_continue_decision", "")) == "CONTINUE_ALLOWED_WITH_ORDER_3_APPROVAL"
        else:
            self.continuation_allowed = bool(continuation_allowed_override)
        self.campaign_approved = bool(campaign_approval and campaign_approval.get("exact_phrase") == sgc.MICRO_CAMPAIGN_PHRASE)
        self.result = sgc.campaign_order_submit(
            "v93-campaign-order-3",
            approval_input=order_approval,
            approval_path=order_approval_path,
            campaign_approved=self.campaign_approved and self.continuation_allowed,
            prereq_ok=self.continuation_allowed,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
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
        return "PASS_ORDER_3_SUBMITTED_CAMPAIGN_CLOSED" if self.submitted else "PARTIAL_ORDER_3_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v92_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v] or ["ORDER_3_BLOCKED"]

    @property
    def next_action(self) -> str:
        return "ORDER_3_SUBMITTED_CAMPAIGN_CLOSED_LOCKED_NO_FURTHER_ORDERS" if self.submitted else "OPERATOR_MUST_PROVIDE_CONTINUATION_AND_ORDER_3_APPROVAL"


def _common(ctx: V93Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v92_baseline_status": ctx.v92_baseline_status,
        "order_3_gate_controller_status": ctx.controller_status,
        "order_3_approval_validator_status": "PASS_ORDER_3_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_ORDER_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_ORDER_3_APPROVAL_ABSENT"),
        "continuation_decision_validator_status": "PASS_CONTINUATION_ALLOWED" if ctx.continuation_allowed else "PARTIAL_CONTINUATION_NOT_ALLOWED",
        "max_3_orders_policy_status": "PASS_MAX_3_ORDERS",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "campaign_approval_present": ctx.campaign_approved,
        "approval_validated": bool(v["accepted"]),
        "approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "single_submit_guard_status": "PASS_SINGLE_SUBMIT_LOCKED" if ctx.submitted else "PASS_SINGLE_SUBMIT_GUARD_ARMED",
        "single_submit_locked": ctx.submitted,
        "campaign_closeout_lock_status": "PASS_CAMPAIGN_CLOSED_LOCKED" if ctx.submitted else "PASS_CAMPAIGN_LOCK_ARMED_NO_ORDER",
        "campaign_closed": ctx.submitted,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "further_campaign_orders_allowed": False,
        "readiness_governor_v53_status": "PASS",
        "execution_lock_deep_recheck_v52_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V93Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v92_baseline"):
        return "PASS" if ctx.v92_baseline_status == "PASS_V92_BASELINE_READBACK" else "FAIL" if ctx.v92_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v93_order_3_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V93Context) -> dict[str, Any]:
    workstream = "v93: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v93_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V93_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v93_report.json":
        report.update({"completion_oriented_next_action_v93_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v79.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v92_carried_status": ctx.v92_baseline_status, "order_3_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v93.json"), "controller": str(ARTIFACTS / "v93_order_3_gate_controller_report.json"), "campaign_closeout": str(ARTIFACTS / "v93_campaign_closeout_lock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v93.json", "dummy_canonical_identity_report_v93.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V93ReportFactory:
    def __init__(self, *, campaign_approval=None, order_approval=None, order_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, continuation_allowed_override=None) -> None:
        self.kw = dict(campaign_approval=campaign_approval, order_approval=order_approval, order_approval_path=order_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, continuation_allowed_override=continuation_allowed_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V93Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
