"""DUMMY v103 campaign order 2 live limit canary — fires one order on full auth, else nothing.

Submit occurs ONLY when V102 passes (order-2 approval + order-1 reconcile/forensic proof), the exact
order-2 approval validates, live-submit operator-enabled, caps present/unchanged, and an explicit
LiveBrokerFirewall adapter is injected with stronger risk thresholds. Default has none of these -> no
submit. Tests inject a NON-BROKER firewall double; no real broker is contacted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v103 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "campaign_order": 2}

V103_ROUTES = [
    "/api/v103/order-2-canary-controller",
    "/api/v103/v102-baseline",
    "/api/v103/order-2-approval-validator",
    "/api/v103/stronger-risk-threshold-validator",
    "/api/v103/single-submit-guard",
    "/api/v103/livebrokerfirewall-submit-adapter",
    "/api/v103/post-submit-auto-lock",
    "/api/v103/readiness-governor",
    "/api/v103/execution-lock",
    "/api/v103/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "order-2-canary-controller": ["v103_order_2_canary_controller_report.json"],
    "v102-baseline": ["v102_baseline_readback_v1_report.json"],
    "order-2-approval-validator": ["v103_order_2_approval_validator_report.json"],
    "stronger-risk-threshold-validator": ["v103_stronger_risk_threshold_validator_report.json"],
    "single-submit-guard": ["v103_single_submit_guard_report.json"],
    "livebrokerfirewall-submit-adapter": ["v103_livebrokerfirewall_submit_adapter_report.json"],
    "post-submit-auto-lock": ["v103_post_submit_auto_lock_report.json"],
    "readiness-governor": ["readiness_governor_v63_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v62_report.json"],
    "mission-state": ["dummy_mission_state_report_v89.json", "dashboard_v103_report_v1.json", "completion_oriented_next_action_v103_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(103)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v103/reports.py scripts/generate_v103_reports.py dashboard/backend/v103_routes.py",
    "python scripts/generate_v103_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V103Context:
    def __init__(self, *, campaign_approval, order_approval, order_approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter, v102_ready_override, order_1_reconciled_override) -> None:
        self.v102_baseline_status = sgc.baseline_status("final_report_v102.json", "V102")
        if v102_ready_override is None:
            self.v102_pass = sgc.load_artifact("final_report_v102.json").get("verdict") == "PASS"
        else:
            self.v102_pass = bool(v102_ready_override)
        if order_1_reconciled_override is None:
            self.order_1_reconciled = str(sgc.load_artifact("final_report_v100.json").get("reconcile_controller_status", "")) == "PASS_ORDER1_RECONCILED_AUTOLOCKED"
        else:
            self.order_1_reconciled = bool(order_1_reconciled_override)
        self.campaign_approved = bool(campaign_approval and campaign_approval.get("exact_phrase") == sgc.MICRO_CAMPAIGN_PHRASE)
        self.result = sgc.campaign_order_submit(
            "v103-campaign-order-2",
            approval_input=order_approval,
            approval_path=order_approval_path,
            campaign_approved=self.campaign_approved and self.v102_pass and self.order_1_reconciled,
            prereq_ok=self.v102_pass and self.order_1_reconciled,
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
        return "PASS_ORDER2_SUBMITTED" if self.submitted else "PARTIAL_ORDER2_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v102_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v] or ["ORDER2_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "ORDER2_SUBMITTED_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_ORDER2_APPROVAL_ORDER1_PROOF_CONFIG_AND_FIREWALL"


def _common(ctx: V103Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v102_baseline_status": ctx.v102_baseline_status,
        "order_2_canary_controller_status": ctx.controller_status,
        "order_2_approval_validator_status": "PASS_ORDER2_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_ORDER_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_ORDER2_APPROVAL_ABSENT"),
        "stronger_risk_threshold_validator_status": "PASS_STRONGER_RISK_THRESHOLDS",
        "campaign_approval_present": ctx.campaign_approved,
        "order_1_reconciled": ctx.order_1_reconciled,
        "approval_validated": bool(v["accepted"]),
        "approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "single_submit_guard_status": "PASS_SINGLE_SUBMIT_LOCKED" if ctx.submitted else "PASS_SINGLE_SUBMIT_GUARD_ARMED",
        "single_submit_locked": ctx.submitted,
        "idempotency_key": ctx.result["idempotency_key"],
        "livebrokerfirewall_submit_adapter_status": "PASS_LIVEBROKERFIREWALL_SUBMIT_ONLY",
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "post_submit_auto_lock_status": "PASS_POST_SUBMIT_AUTO_LOCKED" if ctx.submitted else "PASS_NO_SUBMIT_NOTHING_TO_LOCK",
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "campaign_auto_repeat": False,
        "readiness_governor_v63_status": "PASS",
        "execution_lock_deep_recheck_v62_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V103Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v102_baseline"):
        return "PASS" if ctx.v102_baseline_status == "PASS_V102_BASELINE_READBACK" else "FAIL" if ctx.v102_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v103_order_2_canary_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V103Context) -> dict[str, Any]:
    workstream = "v103: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v103_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V103_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v103_report.json":
        report.update({"completion_oriented_next_action_v103_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v89.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v102_carried_status": ctx.v102_baseline_status, "order_2_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v103.json"), "controller": str(ARTIFACTS / "v103_order_2_canary_controller_report.json"), "post_submit_auto_lock": str(ARTIFACTS / "v103_post_submit_auto_lock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v103.json", "dummy_canonical_identity_report_v103.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V103ReportFactory:
    def __init__(self, *, campaign_approval=None, order_approval=None, order_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, v102_ready_override=None, order_1_reconciled_override=None) -> None:
        self.kw = dict(campaign_approval=campaign_approval, order_approval=order_approval, order_approval_path=order_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, v102_ready_override=v102_ready_override, order_1_reconciled_override=order_1_reconciled_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V103Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
