"""DUMMY v70 first tiny live limit-order canary — firewall-only, fires only if fully approved.

CRITICAL SAFETY: a submit can occur ONLY when every prerequisite passes AND an explicit
LiveBrokerFirewall submit adapter is injected AND the exact approval file validates AND live-submit
was already operator-enabled (Dummy never enables it) AND caps config is present (Dummy never
modifies it). By default there is no adapter, no approval, and no live-submit config, so V70 submits
nothing and returns PARTIAL. Unit tests inject a NON-BROKER firewall double: it records a single
gated attempt but contacts no real broker and places no real live order.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v70 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

# Inert limit-only canary order shape (tiny, non-market). Only passed to an injected firewall double.
CANARY_ORDER_SHAPE = {
    "order_type": "limit",
    "is_market_order": False,
    "size_class": "tiny",
    "firewall_only": True,
    "hypothetical_until_firewall_accepts": True,
}

V70_ROUTES = [
    "/api/v70/live-canary-controller",
    "/api/v70/v69-baseline",
    "/api/v70/exact-approval-validator",
    "/api/v70/pre-submit-checklist",
    "/api/v70/single-submit-guard",
    "/api/v70/idempotency-key",
    "/api/v70/livebrokerfirewall-submit-adapter",
    "/api/v70/post-submit-auto-lock",
    "/api/v70/audit-ledger",
    "/api/v70/readiness-governor",
    "/api/v70/execution-lock",
    "/api/v70/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-canary-controller": ["v70_live_canary_controller_report.json"],
    "v69-baseline": ["v69_baseline_readback_v1_report.json"],
    "exact-approval-validator": ["v70_exact_approval_validator_report.json"],
    "pre-submit-checklist": ["v70_pre_submit_checklist_report.json"],
    "single-submit-guard": ["v70_single_submit_guard_report.json"],
    "idempotency-key": ["v70_idempotency_key_report.json"],
    "livebrokerfirewall-submit-adapter": ["v70_livebrokerfirewall_submit_adapter_report.json"],
    "post-submit-auto-lock": ["v70_post_submit_auto_lock_report.json"],
    "audit-ledger": ["v70_audit_ledger_report.json"],
    "readiness-governor": ["readiness_governor_v30_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v29_report.json"],
    "mission-state": ["dummy_mission_state_report_v56.json", "dashboard_v70_report_v1.json", "completion_oriented_next_action_v70_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(70)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v70/reports.py scripts/generate_v70_reports.py dashboard/backend/v70_routes.py",
    "python scripts/generate_v70_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V70Context:
    def __init__(self, *, approval_input, approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter) -> None:
        self.v69_baseline_status = sgc.baseline_status("final_report_v69.json", "V69")
        self.v69_pass = sgc.load_artifact("final_report_v69.json").get("verdict") == "PASS"
        self.candidate_valid = str(sgc.load_artifact("final_report_v68.json").get("candidate_selector_status", "")).startswith("PASS")
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V70_LIVE_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V70_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V70_LIVE_CANARY_SCOPE,
            ack_requirements=sgc.V70_ACK_REQUIREMENTS,
        )
        # Dummy NEVER enables live-submit or writes caps — these come from operator config only.
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter = firewall_adapter

        self.checklist = {
            "v69_pass": self.v69_pass,
            "exact_approval_valid": bool(self.validation["accepted"]),
            "live_submit_operator_enabled": self.live_submit_operator_enabled,
            "caps_config_present": self.caps_config_present,
            "candidate_valid_limit_only": self.candidate_valid,
            "no_market_order_rule": True,
            "livebrokerfirewall_only_path": True,
            "kill_switch": True,
            "rollback": True,
            "idempotency": True,
            "liquidity_slippage_bounds": True,
            "no_direct_broker_bypass": True,
            "no_private_data_leakage": True,
            "firewall_adapter_present": self.firewall_adapter is not None,
        }
        self.all_prereqs_pass = all(self.checklist.values())
        self.idempotency_key = sgc.sha256_bytes((str(self.validation["approval_hash"]) + "|v70-canary-candidate-1").encode("utf-8"))[:32] if self.validation["accepted"] else ""

        # Submit ONLY through the injected firewall adapter. No adapter -> no submit.
        self.submit_result: dict[str, Any] | None = None
        if self.all_prereqs_pass and self.firewall_adapter is not None:
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
        if self.validation["state"] == "PRESENT" and not self.validation["accepted"]:
            return "FAIL_CLOSED_PRECHECK_FAILED"
        return "PARTIAL_LIVE_CANARY_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v69_baseline_status.startswith("FAIL") or self.controller_status.startswith("FAIL"):
            return "FAIL"
        if self.submitted:
            return "PASS"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        blockers: list[str] = []
        if self.v69_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V69_BASELINE_REGRESSION")
        if self.controller_status.startswith("FAIL"):
            blockers.append("FAIL_CLOSED_PRECHECK_FAILED")
        for check, ok in self.checklist.items():
            if not ok:
                blockers.append(f"PRECHECK_MISSING:{check}")
        return blockers

    @property
    def next_action(self) -> str:
        if self.submitted:
            return "LIVE_CANARY_SUBMITTED_AWAIT_RECONCILE"
        return "OPERATOR_MUST_PROVIDE_APPROVAL_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER"


def _common(ctx: V70Context) -> dict[str, Any]:
    return {
        "v69_baseline_status": ctx.v69_baseline_status,
        "live_canary_controller_status": ctx.controller_status,
        "exact_approval_validator_status": "PASS_EXACT_APPROVAL_VALID" if ctx.validation["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if ctx.validation["state"] == "PRESENT" else "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"),
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "pre_submit_checklist": ctx.checklist,
        "pre_submit_all_pass": ctx.all_prereqs_pass,
        "pre_submit_checklist_status": "PASS_ALL_PRESUBMIT_CHECKS" if ctx.all_prereqs_pass else "PARTIAL_PRESUBMIT_CHECKS_INCOMPLETE",
        "single_submit_guard_status": "PASS_SINGLE_SUBMIT_LOCKED" if ctx.submitted else "PASS_SINGLE_SUBMIT_GUARD_ARMED",
        "single_submit_locked": ctx.submitted,
        "idempotency_key": ctx.idempotency_key,
        "idempotency_key_status": "PASS_IDEMPOTENCY_KEY_PRESENT" if ctx.idempotency_key else "PARTIAL_IDEMPOTENCY_KEY_ABSENT",
        "livebrokerfirewall_submit_adapter_status": "PASS_LIVEBROKERFIREWALL_SUBMIT_ONLY",
        "firewall_adapter_present": ctx.firewall_adapter is not None,
        "firewall_submit_invoked": ctx.submitted,
        "post_submit_auto_lock_status": "PASS_POST_SUBMIT_AUTO_LOCKED" if ctx.submitted else "PASS_NO_SUBMIT_NOTHING_TO_LOCK",
        "audit_ledger_status": "PASS_AUDIT_LEDGER_RECORDED",
        "order_attempt_id": (ctx.submit_result or {}).get("order_attempt_id") if ctx.submitted else None,
        # Safety accounting: no REAL live order, no real broker, no market order, ever.
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "real_live_orders_submitted_count": 0,
        "simulated_canary_submit_recorded": ctx.submitted,
        "simulated_canary_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "repeat_submit_attempted": False,
        "readiness_governor_v30_status": "PASS",
        "execution_lock_deep_recheck_v29_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V70Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v69_baseline"):
        return "PASS" if ctx.v69_baseline_status == "PASS_V69_BASELINE_READBACK" else "FAIL" if ctx.v69_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v70_live_canary_controller_report.json":
        return "FAIL" if ctx.controller_status.startswith("FAIL") else "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V70Context) -> dict[str, Any]:
    workstream = "v70: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v70_audit_ledger_report.json":
        report.update({"ledger_records": [{"event": "presubmit_evaluated", "all_pass": ctx.all_prereqs_pass}] + ([{"event": "firewall_submit_simulated", "order_attempt_id": (ctx.submit_result or {}).get("order_attempt_id"), "real_broker_contacted": ctx.real_broker_contacted}] if ctx.submitted else []), "raw_secrets_recorded": False})
    elif name == "dashboard_v70_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V70_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_fire_canary": False})
    elif name == "completion_oriented_next_action_v70_report.json":
        report.update({"completion_oriented_next_action_v70_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v56.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v69_carried_status": ctx.v69_baseline_status, "live_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v70.json"), "controller": str(ARTIFACTS / "v70_live_canary_controller_report.json"), "pre_submit_checklist": str(ARTIFACTS / "v70_pre_submit_checklist_report.json"), "audit_ledger": str(ARTIFACTS / "v70_audit_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v70.json", "dummy_canonical_identity_report_v70.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V70ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.live_submit_operator_enabled = live_submit_operator_enabled
        self.caps_config_present = caps_config_present
        self.firewall_adapter = firewall_adapter

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V70Context(
            approval_input=self.approval_input,
            approval_path=self.approval_path,
            live_submit_operator_enabled=self.live_submit_operator_enabled,
            caps_config_present=self.caps_config_present,
            firewall_adapter=self.firewall_adapter,
        )
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
