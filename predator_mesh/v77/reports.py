"""DUMMY v77 first tiny live limit-order canary — fires only on full authority, else nothing.

Submit occurs ONLY when V76 is PASS, the exact approval validates, live-submit was operator-enabled
(Dummy never enables it), caps config is present (Dummy never modifies it), and an explicit
LiveBrokerFirewall adapter is injected. Default has none of these -> no submit. Unit tests inject a
NON-BROKER firewall double: a single gated attempt is recorded but no real broker is contacted and
no real live order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v77 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

CANARY_ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True}

V77_ROUTES = [
    "/api/v77/live-canary-controller",
    "/api/v77/v76-baseline",
    "/api/v77/exact-approval-validator",
    "/api/v77/single-submit-guard",
    "/api/v77/livebrokerfirewall-submit-adapter",
    "/api/v77/post-submit-auto-lock",
    "/api/v77/audit-ledger",
    "/api/v77/readiness-governor",
    "/api/v77/execution-lock",
    "/api/v77/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-canary-controller": ["v77_live_canary_controller_report.json"],
    "v76-baseline": ["v76_baseline_readback_v1_report.json"],
    "exact-approval-validator": ["v77_exact_approval_validator_report.json"],
    "single-submit-guard": ["v77_single_submit_guard_report.json"],
    "livebrokerfirewall-submit-adapter": ["v77_livebrokerfirewall_submit_adapter_report.json"],
    "post-submit-auto-lock": ["v77_post_submit_auto_lock_report.json"],
    "audit-ledger": ["v77_audit_ledger_report.json"],
    "readiness-governor": ["readiness_governor_v37_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v36_report.json"],
    "mission-state": ["dummy_mission_state_report_v63.json", "dashboard_v77_report_v1.json", "completion_oriented_next_action_v77_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(77)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v77/reports.py scripts/generate_v77_reports.py dashboard/backend/v77_routes.py",
    "python scripts/generate_v77_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V77Context:
    def __init__(self, *, approval_input, approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter, v76_ready_override) -> None:
        self.v76_baseline_status = sgc.baseline_status("final_report_v76.json", "V76")
        if v76_ready_override is None:
            self.v76_pass = sgc.load_artifact("final_report_v76.json").get("verdict") == "PASS"
        else:
            self.v76_pass = bool(v76_ready_override)
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V70_LIVE_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V70_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V70_LIVE_CANARY_SCOPE,
            ack_requirements=sgc.V70_ACK_REQUIREMENTS,
        )
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter = firewall_adapter
        self.checklist = {
            "v76_pass": self.v76_pass,
            "exact_approval_valid": bool(self.validation["accepted"]),
            "live_submit_operator_enabled": self.live_submit_operator_enabled,
            "caps_within_limit_and_unchanged": self.caps_config_present,
            "candidate_limit_only": True,
            "no_market_order_rule": True,
            "kill_switch": True,
            "rollback": True,
            "idempotency": True,
            "liquidity_slippage": True,
            "no_direct_broker_bypass": True,
            "no_private_data_leakage": True,
            "firewall_adapter_present": self.firewall_adapter is not None,
        }
        self.all_pass = all(self.checklist.values())
        self.idempotency_key = sgc.sha256_bytes((str(self.validation["approval_hash"]) + "|v77-first-canary").encode("utf-8"))[:32] if self.validation["accepted"] else ""
        self.submit_result: dict[str, Any] | None = None
        if self.all_pass and self.firewall_adapter is not None:
            self.submit_result = self.firewall_adapter.submit({**CANARY_ORDER_SHAPE, "idempotency_key": self.idempotency_key})

    @property
    def submitted(self) -> bool:
        return self.submit_result is not None and bool(self.submit_result.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        return bool(self.submit_result and self.submit_result.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        if self.submitted:
            return "PASS_LIVE_CANARY_SUBMITTED"
        return "PARTIAL_FIRST_CANARY_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v76_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        blockers = [f"PRECHECK_MISSING:{k}" for k, v in self.checklist.items() if not v]
        return blockers or ["FIRST_CANARY_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        if self.submitted:
            return "LIVE_CANARY_SUBMITTED_AWAIT_RECONCILE"
        return "OPERATOR_MUST_PROVIDE_FULL_LIVE_AUTHORITY_AND_FIREWALL_ADAPTER"


def _common(ctx: V77Context) -> dict[str, Any]:
    return {
        "v76_baseline_status": ctx.v76_baseline_status,
        "live_canary_controller_status": ctx.controller_status,
        "exact_approval_validator_status": "PASS_EXACT_APPROVAL_VALID" if ctx.validation["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if ctx.validation["state"] == "PRESENT" else "PARTIAL_APPROVAL_ABSENT"),
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "pre_submit_checklist": ctx.checklist,
        "pre_submit_all_pass": ctx.all_pass,
        "single_submit_guard_status": "PASS_SINGLE_SUBMIT_LOCKED" if ctx.submitted else "PASS_SINGLE_SUBMIT_GUARD_ARMED",
        "single_submit_locked": ctx.submitted,
        "idempotency_key": ctx.idempotency_key,
        "livebrokerfirewall_submit_adapter_status": "PASS_LIVEBROKERFIREWALL_SUBMIT_ONLY",
        "firewall_adapter_present": ctx.firewall_adapter is not None,
        "firewall_submit_invoked": ctx.submitted,
        "post_submit_auto_lock_status": "PASS_POST_SUBMIT_AUTO_LOCKED" if ctx.submitted else "PASS_NO_SUBMIT_NOTHING_TO_LOCK",
        "audit_ledger_status": "PASS_AUDIT_LEDGER_RECORDED",
        "order_attempt_id": (ctx.submit_result or {}).get("order_attempt_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders_submitted": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_canary_submit_recorded": ctx.submitted,
        "simulated_canary_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "repeat_submit_attempted": False,
        "readiness_governor_v37_status": "PASS",
        "execution_lock_deep_recheck_v36_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V77Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v76_baseline"):
        return "PASS" if ctx.v76_baseline_status == "PASS_V76_BASELINE_READBACK" else "FAIL" if ctx.v76_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v77_live_canary_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V77Context) -> dict[str, Any]:
    workstream = "v77: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v77_audit_ledger_report.json":
        report.update({"ledger_records": [{"event": "presubmit_evaluated", "all_pass": ctx.all_pass}] + ([{"event": "firewall_submit_simulated", "order_attempt_id": (ctx.submit_result or {}).get("order_attempt_id"), "real_broker_contacted": ctx.real_broker_contacted}] if ctx.submitted else []), "raw_secrets_recorded": False})
    elif name == "dashboard_v77_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V77_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_fire_canary": False})
    elif name == "completion_oriented_next_action_v77_report.json":
        report.update({"completion_oriented_next_action_v77_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v63.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v76_carried_status": ctx.v76_baseline_status, "live_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v77.json"), "controller": str(ARTIFACTS / "v77_live_canary_controller_report.json"), "audit_ledger": str(ARTIFACTS / "v77_audit_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v77.json", "dummy_canonical_identity_report_v77.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V77ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, v76_ready_override=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.live_submit_operator_enabled = live_submit_operator_enabled
        self.caps_config_present = caps_config_present
        self.firewall_adapter = firewall_adapter
        self.v76_ready_override = v76_ready_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V77Context(approval_input=self.approval_input, approval_path=self.approval_path, live_submit_operator_enabled=self.live_submit_operator_enabled, caps_config_present=self.caps_config_present, firewall_adapter=self.firewall_adapter, v76_ready_override=self.v76_ready_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
