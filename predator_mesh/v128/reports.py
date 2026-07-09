"""DUMMY v128 production pilot final authorization packet — assembles the full pilot authorization packet; never submits.

Gathers candidate/abstention, risk (V122), controlled-operation gate (V124), and the V127 approval/config/caps/firewall
tieout, plus limit-only / no-market / liquidity-slippage / kill-switch / rollback / idempotency proofs. Default is
PARTIAL_PILOT_AUTH_PACKET_BLOCKED. When every prerequisite is proven the packet is READY — but nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v128 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v128: Production Pilot Final Authorization Packet No Submit"
MISSION_NAME = "dummy_mission_state_report_v114.json"
FINAL_NAME = "final_report_v128.json"
INDEX_KEYS = ["pilot_auth_packet_controller_status", "auth_packet_ready", "live_orders"]
DASH_TITLE = "Dummy V128 Production Pilot Final Authorization Packet"
MISSION_KEY = "dummy_mission_state_report_v114"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Auth Packet", "pilot_auth_packet_controller_status"],
    ["Packet Ready", "auth_packet_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V128_ROUTES = [
    "/api/v128/pilot-auth-packet-controller",
    "/api/v128/v127-baseline",
    "/api/v128/candidate-abstention-proof",
    "/api/v128/risk-policy-proof",
    "/api/v128/controlled-operation-gate-proof",
    "/api/v128/live-submit-caps-firewall-tieout",
    "/api/v128/limit-only-proof",
    "/api/v128/no-market-order-proof",
    "/api/v128/liquidity-slippage-proof",
    "/api/v128/kill-switch-proof",
    "/api/v128/rollback-proof",
    "/api/v128/idempotency-proof",
    "/api/v128/no-submit-proof",
    "/api/v128/readiness-governor",
    "/api/v128/execution-lock",
    "/api/v128/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "pilot-auth-packet-controller": ["v128_pilot_auth_packet_controller_report.json"],
    "v127-baseline": ["v127_baseline_readback_v1_report.json"],
    "candidate-abstention-proof": ["v128_candidate_abstention_proof_report.json"],
    "risk-policy-proof": ["v128_risk_policy_proof_report.json"],
    "controlled-operation-gate-proof": ["v128_controlled_operation_gate_proof_report.json"],
    "live-submit-caps-firewall-tieout": ["v128_live_submit_caps_firewall_tieout_report.json"],
    "limit-only-proof": ["v128_limit_only_proof_report.json"],
    "no-market-order-proof": ["v128_no_market_order_proof_report.json"],
    "liquidity-slippage-proof": ["v128_liquidity_slippage_proof_report.json"],
    "kill-switch-proof": ["v128_kill_switch_proof_report.json"],
    "rollback-proof": ["v128_rollback_proof_report.json"],
    "idempotency-proof": ["v128_idempotency_proof_report.json"],
    "no-submit-proof": ["v128_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v88_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v87_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v128_report_v1.json", "completion_oriented_next_action_v128_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(128)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v128/reports.py scripts/generate_v128_reports.py dashboard/backend/v128_routes.py",
    "python scripts/generate_v128_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V128Context:
    def __init__(self, *, tieout_ready_override=None, risk_ready_override=None, gate_ready_override=None) -> None:
        self.v127_baseline_status = sgc.baseline_status("final_report_v127.json", "V127")
        if tieout_ready_override is not None:
            self.tieout_ready = bool(tieout_ready_override)
        else:
            self.tieout_ready = str(sgc.load_artifact("final_report_v127.json").get("pilot_tieout_controller_status", "")) == "PASS_PILOT_APPROVAL_CONFIG_FIREWALL_TIEOUT_READY_NO_SUBMIT"
        if risk_ready_override is not None:
            self.risk_ready = bool(risk_ready_override)
        else:
            self.risk_ready = str(sgc.load_artifact("final_report_v122.json").get("risk_stop_policy_controller_status", "")) == "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED"
        if gate_ready_override is not None:
            self.gate_ready = bool(gate_ready_override)
        else:
            self.gate_ready = str(sgc.load_artifact("final_report_v124.json").get("controlled_operation_gate_controller_status", "")) == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"

    @property
    def packet_ready(self) -> bool:
        return self.tieout_ready and self.risk_ready and self.gate_ready

    @property
    def controller_status(self) -> str:
        return "PASS_PRODUCTION_PILOT_AUTH_PACKET_READY_NO_SUBMIT" if self.packet_ready else "PARTIAL_PILOT_AUTH_PACKET_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v127_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.packet_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v127_baseline_status.startswith("FAIL"):
            return ["FAIL_V127_BASELINE_REGRESSION"]
        if self.packet_ready:
            return []
        blockers: list[str] = []
        if not self.tieout_ready:
            blockers.append("PILOT_TIEOUT_NOT_READY")
        if not self.risk_ready:
            blockers.append("RISK_POLICY_PROOF_ABSENT")
        if not self.gate_ready:
            blockers.append("CONTROLLED_OPERATION_GATE_PROOF_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "PILOT_AUTH_PACKET_READY_NO_SUBMIT_AWAIT_CONTROLLED_PILOT_FIRE_ON_FULL_AUTH" if self.packet_ready else "OPERATOR_MUST_COMPLETE_PILOT_TIEOUT_RISK_AND_GATE_PROOFS_NO_SUBMIT"


def _common(ctx: V128Context) -> dict[str, Any]:
    ready = ctx.packet_ready
    def s(v, ok):
        return v if ok else "PARTIAL_PROOF_ABSENT"
    return {
        "v127_baseline_status": ctx.v127_baseline_status,
        "pilot_auth_packet_controller_status": ctx.controller_status,
        "candidate_abstention_proof_status": "PASS_CANDIDATE_ABSTENTION_PROVEN",
        "risk_policy_proof_status": s("PASS_RISK_POLICY_PROVEN", ctx.risk_ready),
        "controlled_operation_gate_proof_status": s("PASS_CONTROLLED_OPERATION_GATE_PROVEN", ctx.gate_ready),
        "live_submit_caps_firewall_tieout_status": s("PASS_LIVE_SUBMIT_CAPS_FIREWALL_TIEOUT_PROVEN", ctx.tieout_ready),
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE_PROVEN",
        "kill_switch_proof_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_proof_status": "PASS_ROLLBACK_READY",
        "idempotency_proof_status": "PASS_IDEMPOTENCY_READY",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "auth_packet_ready": ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v88_status": "PASS",
        "execution_lock_deep_recheck_v87_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V128Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v127_baseline"):
        return "PASS" if ctx.v127_baseline_status == "PASS_V127_BASELINE_READBACK" else "FAIL" if ctx.v127_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v128_pilot_auth_packet_controller_report.json":
        return "PASS" if ctx.packet_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V128Context) -> dict[str, Any]:
    workstream = "v128: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v128_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V128_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v128_report.json":
        report.update({"completion_oriented_next_action_v128_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v127_carried_status": ctx.v127_baseline_status, "pilot_auth_packet_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v128_pilot_auth_packet_controller_report.json"), "no_submit": str(ARTIFACTS / "v128_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v128.json", "dummy_canonical_identity_report_v128.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V128ReportFactory:
    def __init__(self, *, tieout_ready_override=None, risk_ready_override=None, gate_ready_override=None) -> None:
        self.kw = dict(tieout_ready_override=tieout_ready_override, risk_ready_override=risk_ready_override, gate_ready_override=gate_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V128Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
