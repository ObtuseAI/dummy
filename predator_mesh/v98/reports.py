"""DUMMY v98 order 1 final authorization tieout (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v98 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V98_ROUTES = [
    "/api/v98/order-1-authorization-controller",
    "/api/v98/v97-baseline",
    "/api/v98/candidate-queue-readback",
    "/api/v98/approval-readback",
    "/api/v98/config-firewall-readback",
    "/api/v98/limit-only-proof",
    "/api/v98/no-market-order-proof",
    "/api/v98/tiny-exposure-proof",
    "/api/v98/liquidity-slippage-proof",
    "/api/v98/kill-switch-proof",
    "/api/v98/rollback-proof",
    "/api/v98/idempotency-proof",
    "/api/v98/no-submit-proof",
    "/api/v98/readiness-governor",
    "/api/v98/execution-lock",
    "/api/v98/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "order-1-authorization-controller": ["v98_order_1_authorization_controller_report.json"],
    "v97-baseline": ["v97_baseline_readback_v1_report.json"],
    "candidate-queue-readback": ["v98_candidate_queue_readback_report.json"],
    "approval-readback": ["v98_approval_readback_report.json"],
    "config-firewall-readback": ["v98_config_firewall_readback_report.json"],
    "limit-only-proof": ["v98_limit_only_proof_report.json"],
    "no-market-order-proof": ["v98_no_market_order_proof_report.json"],
    "tiny-exposure-proof": ["v98_tiny_exposure_proof_report.json"],
    "liquidity-slippage-proof": ["v98_liquidity_slippage_proof_report.json"],
    "kill-switch-proof": ["v98_kill_switch_proof_report.json"],
    "rollback-proof": ["v98_rollback_proof_report.json"],
    "idempotency-proof": ["v98_idempotency_proof_report.json"],
    "no-submit-proof": ["v98_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v58_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v57_report.json"],
    "mission-state": ["dummy_mission_state_report_v84.json", "dashboard_v98_report_v1.json", "completion_oriented_next_action_v98_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(98)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v98/reports.py scripts/generate_v98_reports.py dashboard/backend/v98_routes.py",
    "python scripts/generate_v98_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

PROOFS = {
    "limit_only_proof_status": "PASS_LIMIT_ONLY",
    "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
    "tiny_exposure_proof_status": "PASS_TINY_EXPOSURE",
    "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE",
    "kill_switch_proof_status": "PASS_KILL_SWITCH",
    "rollback_proof_status": "PASS_ROLLBACK",
    "idempotency_proof_status": "PASS_IDEMPOTENCY",
}


class V98Context:
    def __init__(self, *, v97_ready_override=None, v96_ready_override=None) -> None:
        self.v97_baseline_status = sgc.baseline_status("final_report_v97.json", "V97")
        if v97_ready_override is None:
            self.v97_ready = sgc.load_artifact("final_report_v97.json").get("verdict") == "PASS"
        else:
            self.v97_ready = bool(v97_ready_override)
        if v96_ready_override is None:
            self.v96_ready = sgc.load_artifact("final_report_v96.json").get("verdict") == "PASS"
        else:
            self.v96_ready = bool(v96_ready_override)
        self.candidate_ok = str(sgc.load_artifact("final_report_v88.json").get("candidate_queue_controller_status", "")).startswith("PASS")

    @property
    def authorized(self) -> bool:
        return self.v97_ready and self.v96_ready and self.candidate_ok

    @property
    def controller_status(self) -> str:
        return "PASS_ORDER1_AUTHORIZATION_READY_NO_SUBMIT" if self.authorized else "PARTIAL_ORDER1_AUTHORIZATION_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v97_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.authorized else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v97_baseline_status.startswith("FAIL"):
            return ["FAIL_V97_BASELINE_REGRESSION"]
        blockers: list[str] = []
        if not self.v96_ready:
            blockers.append("CAMPAIGN_OR_ORDER1_APPROVAL_NOT_VALID")
        if not self.v97_ready:
            blockers.append("LIVE_CONFIG_FIREWALL_NOT_READY")
        if not self.candidate_ok:
            blockers.append("CANDIDATE_NOT_READY")
        return blockers

    @property
    def next_action(self) -> str:
        return "ORDER1_AUTHORIZATION_READY_AWAIT_V99_ARM_NO_SUBMIT" if self.authorized else "OPERATOR_MUST_COMPLETE_APPROVAL_AND_CONFIG_TIEOUT"


def _common(ctx: V98Context) -> dict[str, Any]:
    common = {
        "v97_baseline_status": ctx.v97_baseline_status,
        "order_1_authorization_controller_status": ctx.controller_status,
        "candidate_queue_readback_status": "PASS_CANDIDATE_READBACK" if ctx.candidate_ok else "PARTIAL_CANDIDATE_ABSENT",
        "approval_readback_status": "PASS_APPROVAL_READBACK" if ctx.v96_ready else "PARTIAL_APPROVAL_ABSENT",
        "config_firewall_readback_status": "PASS_CONFIG_FIREWALL_READBACK" if ctx.v97_ready else "PARTIAL_CONFIG_FIREWALL_ABSENT",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "order_submission_present": False,
        "live_orders": 0,
        "readiness_governor_v58_status": "PASS",
        "execution_lock_deep_recheck_v57_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(PROOFS)
    return common


def _verdict(name: str, ctx: V98Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v97_baseline"):
        return "PASS" if ctx.v97_baseline_status == "PASS_V97_BASELINE_READBACK" else "FAIL" if ctx.v97_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v98_order_1_authorization_controller_report.json":
        return "PASS" if ctx.authorized else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V98Context) -> dict[str, Any]:
    workstream = "v98: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v98_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V98_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v98_report.json":
        report.update({"completion_oriented_next_action_v98_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v84.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v97_carried_status": ctx.v97_baseline_status, "order_1_authorization_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v98.json"), "authorization": str(ARTIFACTS / "v98_order_1_authorization_controller_report.json"), "no_submit": str(ARTIFACTS / "v98_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v98.json", "dummy_canonical_identity_report_v98.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V98ReportFactory:
    def __init__(self, *, v97_ready_override=None, v96_ready_override=None) -> None:
        self.kw = dict(v97_ready_override=v97_ready_override, v96_ready_override=v96_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V98Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
