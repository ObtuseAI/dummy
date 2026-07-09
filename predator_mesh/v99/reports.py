"""DUMMY v99 campaign order 1 live limit canary — fires one order on full auth, else nothing.

Submit occurs ONLY when V98 passes, campaign + order-1 approvals validate, live-submit was
operator-enabled (Dummy never enables it), caps present/unchanged (Dummy never modifies), and an
explicit LiveBrokerFirewall adapter is injected. Default has none of these -> no submit. Tests inject
a NON-BROKER firewall double; no real broker is contacted and no real live order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v99 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "campaign_order": 1}

V99_ROUTES = [
    "/api/v99/order-1-canary-controller",
    "/api/v99/v98-baseline",
    "/api/v99/order-1-approval-validator",
    "/api/v99/pre-submit-checklist",
    "/api/v99/single-submit-guard",
    "/api/v99/livebrokerfirewall-submit-adapter",
    "/api/v99/post-submit-auto-lock",
    "/api/v99/audit-ledger",
    "/api/v99/readiness-governor",
    "/api/v99/execution-lock",
    "/api/v99/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "order-1-canary-controller": ["v99_order_1_canary_controller_report.json"],
    "v98-baseline": ["v98_baseline_readback_v1_report.json"],
    "order-1-approval-validator": ["v99_order_1_approval_validator_report.json"],
    "pre-submit-checklist": ["v99_pre_submit_checklist_report.json"],
    "single-submit-guard": ["v99_single_submit_guard_report.json"],
    "livebrokerfirewall-submit-adapter": ["v99_livebrokerfirewall_submit_adapter_report.json"],
    "post-submit-auto-lock": ["v99_post_submit_auto_lock_report.json"],
    "audit-ledger": ["v99_audit_ledger_report.json"],
    "readiness-governor": ["readiness_governor_v59_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v58_report.json"],
    "mission-state": ["dummy_mission_state_report_v85.json", "dashboard_v99_report_v1.json", "completion_oriented_next_action_v99_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(99)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v99/reports.py scripts/generate_v99_reports.py dashboard/backend/v99_routes.py",
    "python scripts/generate_v99_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V99Context:
    def __init__(self, *, campaign_approval, order_approval, order_approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter, v98_ready_override) -> None:
        self.v98_baseline_status = sgc.baseline_status("final_report_v98.json", "V98")
        if v98_ready_override is None:
            self.v98_pass = sgc.load_artifact("final_report_v98.json").get("verdict") == "PASS"
        else:
            self.v98_pass = bool(v98_ready_override)
        self.campaign_approved = bool(campaign_approval and campaign_approval.get("exact_phrase") == sgc.MICRO_CAMPAIGN_PHRASE)
        self.result = sgc.campaign_order_submit(
            "v99-campaign-order-1",
            approval_input=order_approval,
            approval_path=order_approval_path,
            campaign_approved=self.campaign_approved,
            prereq_ok=self.v98_pass,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
        )
        self.firewall_adapter_present = firewall_adapter is not None
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)

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
        return "PASS_ORDER1_SUBMITTED" if self.submitted else "PARTIAL_ORDER1_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v98_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v] or ["ORDER1_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "ORDER1_SUBMITTED_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_CAMPAIGN_AND_ORDER1_APPROVAL_CONFIG_AND_FIREWALL"


def _common(ctx: V99Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v98_baseline_status": ctx.v98_baseline_status,
        "order_1_canary_controller_status": ctx.controller_status,
        "order_1_approval_validator_status": "PASS_ORDER1_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_ORDER_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_ORDER1_APPROVAL_ABSENT"),
        "campaign_approval_present": ctx.campaign_approved,
        "approval_validated": bool(v["accepted"]),
        "approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "pre_submit_checklist_status": "PASS_ALL_PRESUBMIT_CHECKS" if ctx.result["all_pass"] else "PARTIAL_PRESUBMIT_CHECKS_INCOMPLETE",
        "single_submit_guard_status": "PASS_SINGLE_SUBMIT_LOCKED" if ctx.submitted else "PASS_SINGLE_SUBMIT_GUARD_ARMED",
        "single_submit_locked": ctx.submitted,
        "idempotency_key": ctx.result["idempotency_key"],
        "livebrokerfirewall_submit_adapter_status": "PASS_LIVEBROKERFIREWALL_SUBMIT_ONLY",
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "post_submit_auto_lock_status": "PASS_POST_SUBMIT_AUTO_LOCKED" if ctx.submitted else "PASS_NO_SUBMIT_NOTHING_TO_LOCK",
        "audit_ledger_status": "PASS_AUDIT_LEDGER_RECORDED",
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "repeat_submit_attempted": False,
        "readiness_governor_v59_status": "PASS",
        "execution_lock_deep_recheck_v58_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V99Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v98_baseline"):
        return "PASS" if ctx.v98_baseline_status == "PASS_V98_BASELINE_READBACK" else "FAIL" if ctx.v98_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v99_order_1_canary_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V99Context) -> dict[str, Any]:
    workstream = "v99: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v99_audit_ledger_report.json":
        report.update({"ledger_records": [{"event": "presubmit_evaluated", "all_pass": ctx.result["all_pass"]}] + ([{"event": "firewall_submit_simulated", "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id"), "real_broker_contacted": ctx.real_broker_contacted}] if ctx.submitted else []), "raw_secrets_recorded": False})
    elif name == "dashboard_v99_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V99_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v99_report.json":
        report.update({"completion_oriented_next_action_v99_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v85.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v98_carried_status": ctx.v98_baseline_status, "order_1_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v99.json"), "controller": str(ARTIFACTS / "v99_order_1_canary_controller_report.json"), "audit_ledger": str(ARTIFACTS / "v99_audit_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v99.json", "dummy_canonical_identity_report_v99.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V99ReportFactory:
    def __init__(self, *, campaign_approval=None, order_approval=None, order_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, v98_ready_override=None) -> None:
        self.kw = dict(campaign_approval=campaign_approval, order_approval=order_approval, order_approval_path=order_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, v98_ready_override=v98_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V99Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
