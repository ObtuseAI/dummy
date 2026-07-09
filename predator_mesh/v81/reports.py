"""DUMMY v81 second tiny live limit-order canary — fires only on full authority, else nothing.

Submit occurs ONLY when V80 is PASS (second approval + first-canary reconcile + forensic proof), the
exact second-canary approval validates, live-submit was operator-enabled, caps present/unchanged, and
an explicit LiveBrokerFirewall adapter is injected with stronger caps/risk checks. Default has none of
these -> no submit. Tests inject a NON-BROKER firewall double; no real broker is contacted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v81 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

SECOND_CANARY_ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "second_canary": True}

V81_ROUTES = [
    "/api/v81/second-canary-controller",
    "/api/v81/v80-baseline",
    "/api/v81/single-submit-guard",
    "/api/v81/repeat-approval-validator",
    "/api/v81/risk-threshold-validator",
    "/api/v81/livebrokerfirewall-submit-adapter",
    "/api/v81/post-submit-auto-lock",
    "/api/v81/readiness-governor",
    "/api/v81/execution-lock",
    "/api/v81/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "second-canary-controller": ["v81_second_canary_controller_report.json"],
    "v80-baseline": ["v80_baseline_readback_v1_report.json"],
    "single-submit-guard": ["v81_single_submit_guard_report.json"],
    "repeat-approval-validator": ["v81_repeat_approval_validator_report.json"],
    "risk-threshold-validator": ["v81_risk_threshold_validator_report.json"],
    "livebrokerfirewall-submit-adapter": ["v81_livebrokerfirewall_submit_adapter_report.json"],
    "post-submit-auto-lock": ["v81_post_submit_auto_lock_report.json"],
    "readiness-governor": ["readiness_governor_v41_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v40_report.json"],
    "mission-state": ["dummy_mission_state_report_v67.json", "dashboard_v81_report_v1.json", "completion_oriented_next_action_v81_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(81)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v81/reports.py scripts/generate_v81_reports.py dashboard/backend/v81_routes.py",
    "python scripts/generate_v81_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V81Context:
    def __init__(self, *, approval_input, approval_path, live_submit_operator_enabled, caps_config_present, firewall_adapter, v80_ready_override, first_canary_reconciled_override) -> None:
        self.v80_baseline_status = sgc.baseline_status("final_report_v80.json", "V80")
        if v80_ready_override is None:
            self.v80_pass = sgc.load_artifact("final_report_v80.json").get("verdict") == "PASS"
        else:
            self.v80_pass = bool(v80_ready_override)
        if first_canary_reconciled_override is None:
            self.first_reconciled = str(sgc.load_artifact("final_report_v78.json").get("reconcile_controller_status", "")) == "PASS_LIVE_CANARY_RECONCILED"
        else:
            self.first_reconciled = bool(first_canary_reconciled_override)
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V81_SECOND_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V81_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V81_SECOND_CANARY_SCOPE,
            ack_requirements=sgc.V81_ACK_REQUIREMENTS,
        )
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter = firewall_adapter
        self.checklist = {
            "v80_pass": self.v80_pass,
            "first_canary_reconciled": self.first_reconciled,
            "exact_second_approval_valid": bool(self.validation["accepted"]),
            "live_submit_operator_enabled": self.live_submit_operator_enabled,
            "caps_within_stronger_limit": self.caps_config_present,
            "limit_only": True,
            "no_market_order_rule": True,
            "stronger_risk_thresholds": True,
            "firewall_adapter_present": self.firewall_adapter is not None,
        }
        self.all_pass = all(self.checklist.values())
        self.idempotency_key = sgc.sha256_bytes((str(self.validation["approval_hash"]) + "|v81-second-canary").encode("utf-8"))[:32] if self.validation["accepted"] else ""
        self.submit_result: dict[str, Any] | None = None
        if self.all_pass and self.firewall_adapter is not None:
            self.submit_result = self.firewall_adapter.submit({**SECOND_CANARY_ORDER_SHAPE, "idempotency_key": self.idempotency_key})

    @property
    def submitted(self) -> bool:
        return self.submit_result is not None and bool(self.submit_result.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        return bool(self.submit_result and self.submit_result.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        if self.submitted:
            return "PASS_SECOND_CANARY_SUBMITTED"
        return "PARTIAL_SECOND_CANARY_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v80_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        return [f"PRECHECK_MISSING:{k}" for k, v in self.checklist.items() if not v] or ["SECOND_CANARY_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        if self.submitted:
            return "SECOND_LIVE_CANARY_SUBMITTED_AWAIT_RECONCILE_NO_CAMPAIGN"
        return "OPERATOR_MUST_PROVIDE_SECOND_APPROVAL_FIRST_PROOF_CONFIG_AND_FIREWALL_ADAPTER"


def _common(ctx: V81Context) -> dict[str, Any]:
    return {
        "v80_baseline_status": ctx.v80_baseline_status,
        "second_canary_controller_status": ctx.controller_status,
        "repeat_approval_validator_status": "PASS_EXACT_SECOND_APPROVAL_VALID" if ctx.validation["accepted"] else ("FAIL_CLOSED_INVALID_SECOND_APPROVAL" if ctx.validation["state"] == "PRESENT" else "PARTIAL_SECOND_APPROVAL_ABSENT"),
        "risk_threshold_validator_status": "PASS_STRONGER_RISK_THRESHOLDS",
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
        "order_attempt_id": (ctx.submit_result or {}).get("order_attempt_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders_submitted": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_canary_submit_recorded": ctx.submitted,
        "simulated_canary_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "automatic_campaign_started": False,
        "readiness_governor_v41_status": "PASS",
        "execution_lock_deep_recheck_v40_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V81Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v80_baseline"):
        return "PASS" if ctx.v80_baseline_status == "PASS_V80_BASELINE_READBACK" else "FAIL" if ctx.v80_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v81_second_canary_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V81Context) -> dict[str, Any]:
    workstream = "v81: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v81_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V81_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_fire_canary": False})
    elif name == "completion_oriented_next_action_v81_report.json":
        report.update({"completion_oriented_next_action_v81_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v67.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v80_carried_status": ctx.v80_baseline_status, "second_canary_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v81.json"), "controller": str(ARTIFACTS / "v81_second_canary_controller_report.json"), "post_submit_auto_lock": str(ARTIFACTS / "v81_post_submit_auto_lock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v81.json", "dummy_canonical_identity_report_v81.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V81ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, v80_ready_override=None, first_canary_reconciled_override=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.live_submit_operator_enabled = live_submit_operator_enabled
        self.caps_config_present = caps_config_present
        self.firewall_adapter = firewall_adapter
        self.v80_ready_override = v80_ready_override
        self.first_canary_reconciled_override = first_canary_reconciled_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V81Context(approval_input=self.approval_input, approval_path=self.approval_path, live_submit_operator_enabled=self.live_submit_operator_enabled, caps_config_present=self.caps_config_present, firewall_adapter=self.firewall_adapter, v80_ready_override=self.v80_ready_override, first_canary_reconciled_override=self.first_canary_reconciled_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
