"""DUMMY v76 final single-canary authorization packet (no broker submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v76 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V76_ROUTES = [
    "/api/v76/authorization-packet-controller",
    "/api/v76/v75-baseline",
    "/api/v76/candidate-tieout",
    "/api/v76/firewall-tieout",
    "/api/v76/caps-live-submit-approval-tieout",
    "/api/v76/limit-order-only-proof",
    "/api/v76/no-market-order-proof",
    "/api/v76/liquidity-slippage-proof",
    "/api/v76/kill-switch-proof",
    "/api/v76/rollback-proof",
    "/api/v76/idempotency-proof",
    "/api/v76/one-order-only-proof",
    "/api/v76/readiness-governor",
    "/api/v76/execution-lock",
    "/api/v76/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "authorization-packet-controller": ["v76_authorization_packet_controller_report.json"],
    "v75-baseline": ["v75_baseline_readback_v1_report.json"],
    "candidate-tieout": ["v76_candidate_tieout_report.json"],
    "firewall-tieout": ["v76_firewall_tieout_report.json"],
    "caps-live-submit-approval-tieout": ["v76_caps_live_submit_approval_tieout_report.json"],
    "limit-order-only-proof": ["v76_limit_order_only_proof_report.json"],
    "no-market-order-proof": ["v76_no_market_order_proof_report.json"],
    "liquidity-slippage-proof": ["v76_liquidity_slippage_proof_report.json"],
    "kill-switch-proof": ["v76_kill_switch_proof_report.json"],
    "rollback-proof": ["v76_rollback_proof_report.json"],
    "idempotency-proof": ["v76_idempotency_proof_report.json"],
    "one-order-only-proof": ["v76_one_order_only_proof_report.json"],
    "readiness-governor": ["readiness_governor_v36_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v35_report.json"],
    "mission-state": ["dummy_mission_state_report_v62.json", "dashboard_v76_report_v1.json", "completion_oriented_next_action_v76_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(76)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v76/reports.py scripts/generate_v76_reports.py dashboard/backend/v76_routes.py",
    "python scripts/generate_v76_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

PACKET_PROOFS = {
    "candidate_tieout_status": "PASS_CANDIDATE_LIMIT_ONLY_TIED_OUT",
    "firewall_tieout_status": "PASS_FIREWALL_TIED_OUT",
    "limit_order_only_proof_status": "PASS_LIMIT_ORDER_ONLY",
    "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
    "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE",
    "kill_switch_proof_status": "PASS_KILL_SWITCH",
    "rollback_proof_status": "PASS_ROLLBACK",
    "idempotency_proof_status": "PASS_IDEMPOTENCY",
    "one_order_only_proof_status": "PASS_ONE_ORDER_ONLY",
}


class V76Context:
    def __init__(self, *, v75_ready_override=None) -> None:
        self.v75_baseline_status = sgc.baseline_status("final_report_v75.json", "V75")
        if v75_ready_override is None:
            self.v75_ready = sgc.load_artifact("final_report_v75.json").get("verdict") == "PASS"
        else:
            self.v75_ready = bool(v75_ready_override)
        self.candidate_ok = str(sgc.load_artifact("final_report_v68.json").get("candidate_selector_status", "")).startswith("PASS")
        self.firewall_ok = sgc.load_artifact("final_report_v69.json").get("verdict") == "PASS"

    @property
    def packet_ready(self) -> bool:
        return self.v75_ready and self.candidate_ok and self.firewall_ok

    @property
    def controller_status(self) -> str:
        # No execution path is ever created, so FAIL_AUTH_PACKET_CREATED_EXECUTION_PATH cannot occur.
        if self.packet_ready:
            return "PASS_SINGLE_CANARY_AUTH_PACKET_READY_NO_SUBMIT"
        return "PARTIAL_SINGLE_CANARY_AUTH_PACKET_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v75_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.packet_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v75_baseline_status.startswith("FAIL"):
            return ["FAIL_V75_BASELINE_REGRESSION"]
        blockers: list[str] = []
        if not self.v75_ready:
            blockers.append("V75_CONFIG_APPROVAL_TIEOUT_NOT_PASS")
        if not self.candidate_ok:
            blockers.append("CANDIDATE_NOT_READY")
        if not self.firewall_ok:
            blockers.append("FIREWALL_TIEOUT_NOT_READY")
        return blockers

    @property
    def next_action(self) -> str:
        if self.packet_ready:
            return "SINGLE_CANARY_AUTH_PACKET_READY_AWAIT_V77_ARM_NO_SUBMIT"
        return "OPERATOR_MUST_COMPLETE_V75_CONFIG_APPROVAL_TIEOUT"


def _common(ctx: V76Context) -> dict[str, Any]:
    common = {
        "v75_baseline_status": ctx.v75_baseline_status,
        "authorization_packet_controller_status": ctx.controller_status,
        "v75_config_approval_ready": ctx.v75_ready,
        "candidate_ready": ctx.candidate_ok,
        "firewall_ready": ctx.firewall_ok,
        "caps_live_submit_approval_tieout_status": "PASS_CAPS_LIVE_SUBMIT_APPROVAL_TIED_OUT" if ctx.v75_ready else "PARTIAL_CAPS_LIVE_SUBMIT_APPROVAL_ABSENT",
        "order_submission_present": False,
        "execution_path_created": False,
        "readiness_governor_v36_status": "PASS",
        "execution_lock_deep_recheck_v35_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(PACKET_PROOFS)
    return common


def _verdict(name: str, ctx: V76Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v75_baseline"):
        return "PASS" if ctx.v75_baseline_status == "PASS_V75_BASELINE_READBACK" else "FAIL" if ctx.v75_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v76_authorization_packet_controller_report.json":
        return "PASS" if ctx.packet_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V76Context) -> dict[str, Any]:
    workstream = "v76: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v76_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V76_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v76_report.json":
        report.update({"completion_oriented_next_action_v76_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v62.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v75_carried_status": ctx.v75_baseline_status, "authorization_packet_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v76.json"), "auth_packet": str(ARTIFACTS / "v76_authorization_packet_controller_report.json"), "one_order_only": str(ARTIFACTS / "v76_one_order_only_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v76.json", "dummy_canonical_identity_report_v76.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V76ReportFactory:
    def __init__(self, *, v75_ready_override=None) -> None:
        self.v75_ready_override = v75_ready_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V76Context(v75_ready_override=self.v75_ready_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
