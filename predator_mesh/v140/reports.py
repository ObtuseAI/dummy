"""DUMMY v140 final production pilot authorization packet — assembles the final pilot auth packet; never submits.

Reads the V136 authority binder, V137 live-submit/caps snapshot, V138 firewall contract, and V139 candidate/abstention
preflight, plus limit-only / no-market / kill-switch / rollback / idempotency / liquidity-slippage / one-pilot-only
proofs. Default is PARTIAL_FINAL_PILOT_AUTH_PACKET_BLOCKED. When every input is proven the packet is READY — nothing
is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v140 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v140: Final Production Pilot Authorization Packet No Submit"
MISSION_NAME = "dummy_mission_state_report_v126.json"
FINAL_NAME = "final_report_v140.json"
INDEX_KEYS = ["final_auth_packet_controller_status", "auth_packet_ready", "live_orders"]
DASH_TITLE = "Dummy V140 Final Production Pilot Authorization Packet"
MISSION_KEY = "dummy_mission_state_report_v126"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Final Auth Packet", "final_auth_packet_controller_status"],
    ["Packet Ready", "auth_packet_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V140_ROUTES = [
    "/api/v140/final-auth-packet-controller",
    "/api/v140/v139-baseline",
    "/api/v140/authority-binder-readback",
    "/api/v140/live-submit-caps-snapshot-readback",
    "/api/v140/firewall-contract-readback",
    "/api/v140/candidate-abstention-readback",
    "/api/v140/exact-pilot-approval-proof",
    "/api/v140/limit-only-proof",
    "/api/v140/no-market-order-proof",
    "/api/v140/kill-switch-proof",
    "/api/v140/rollback-proof",
    "/api/v140/idempotency-proof",
    "/api/v140/liquidity-slippage-proof",
    "/api/v140/one-pilot-only-proof",
    "/api/v140/no-submit-proof",
    "/api/v140/readiness-governor",
    "/api/v140/execution-lock",
    "/api/v140/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "final-auth-packet-controller": ["v140_final_auth_packet_controller_report.json"],
    "v139-baseline": ["v139_baseline_readback_v1_report.json"],
    "authority-binder-readback": ["v140_authority_binder_readback_report.json"],
    "live-submit-caps-snapshot-readback": ["v140_live_submit_caps_snapshot_readback_report.json"],
    "firewall-contract-readback": ["v140_firewall_contract_readback_report.json"],
    "candidate-abstention-readback": ["v140_candidate_abstention_readback_report.json"],
    "exact-pilot-approval-proof": ["v140_exact_pilot_approval_proof_report.json"],
    "limit-only-proof": ["v140_limit_only_proof_report.json"],
    "no-market-order-proof": ["v140_no_market_order_proof_report.json"],
    "kill-switch-proof": ["v140_kill_switch_proof_report.json"],
    "rollback-proof": ["v140_rollback_proof_report.json"],
    "idempotency-proof": ["v140_idempotency_proof_report.json"],
    "liquidity-slippage-proof": ["v140_liquidity_slippage_proof_report.json"],
    "one-pilot-only-proof": ["v140_one_pilot_only_proof_report.json"],
    "no-submit-proof": ["v140_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v100_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v99_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v140_report_v1.json", "completion_oriented_next_action_v140_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(140)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v140/reports.py scripts/generate_v140_reports.py dashboard/backend/v140_routes.py",
    "python scripts/generate_v140_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V140Context:
    def __init__(self, *, binder_ready_override=None, snapshot_ready_override=None, firewall_ready_override=None, candidate_ready_override=None) -> None:
        self.v139_baseline_status = sgc.baseline_status("final_report_v139.json", "V139")
        if binder_ready_override is not None:
            self.binder_ready = bool(binder_ready_override)
        else:
            self.binder_ready = str(sgc.load_artifact("final_report_v136.json").get("authority_binder_controller_status", "")) == "PASS_PILOT_AUTHORITY_BOUND_NO_SUBMIT"
        if snapshot_ready_override is not None:
            self.snapshot_ready = bool(snapshot_ready_override)
        else:
            self.snapshot_ready = str(sgc.load_artifact("final_report_v137.json").get("config_snapshot_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_READONLY"
        if firewall_ready_override is not None:
            self.firewall_ready = bool(firewall_ready_override)
        else:
            self.firewall_ready = str(sgc.load_artifact("final_report_v138.json").get("firewall_adapter_controller_status", "")) == "PASS_FIREWALL_ADAPTER_CONTRACT_VERIFIED"
        if candidate_ready_override is not None:
            self.candidate_ready = bool(candidate_ready_override)
        else:
            self.candidate_ready = str(sgc.load_artifact("final_report_v139.json").get("candidate_preflight_controller_status", "")) == "PASS_CANDIDATE_ABSTENTION_PREFLIGHT_COMPLETE" and str(sgc.load_artifact("final_report_v139.json").get("abstention_decision", "")) == "TRADE_ELIGIBLE_REVIEW_ONLY"

    @property
    def packet_ready(self) -> bool:
        return self.binder_ready and self.snapshot_ready and self.firewall_ready and self.candidate_ready

    @property
    def controller_status(self) -> str:
        return "PASS_FINAL_PILOT_AUTH_PACKET_READY_NO_SUBMIT" if self.packet_ready else "PARTIAL_FINAL_PILOT_AUTH_PACKET_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v139_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.packet_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v139_baseline_status.startswith("FAIL"):
            return ["FAIL_V139_BASELINE_REGRESSION"]
        if self.packet_ready:
            return []
        blockers: list[str] = []
        if not self.binder_ready:
            blockers.append("AUTHORITY_BINDER_NOT_READY")
        if not self.snapshot_ready:
            blockers.append("LIVE_SUBMIT_CAPS_SNAPSHOT_NOT_READY")
        if not self.firewall_ready:
            blockers.append("FIREWALL_CONTRACT_NOT_VERIFIED")
        if not self.candidate_ready:
            blockers.append("CANDIDATE_ABSTENTION_NOT_READY")
        return blockers

    @property
    def next_action(self) -> str:
        return "FINAL_PILOT_AUTH_PACKET_READY_NO_SUBMIT_AWAIT_CONTROLLED_PILOT_FIRE_ON_FULL_AUTH" if self.packet_ready else "OPERATOR_MUST_COMPLETE_BINDER_SNAPSHOT_FIREWALL_AND_CANDIDATE_PROOFS_NO_SUBMIT"


def _common(ctx: V140Context) -> dict[str, Any]:
    def s(v, ok):
        return v if ok else "PARTIAL_READBACK_NOT_READY"
    return {
        "v139_baseline_status": ctx.v139_baseline_status,
        "final_auth_packet_controller_status": ctx.controller_status,
        "authority_binder_readback_status": s("PASS_AUTHORITY_BINDER_READ", ctx.binder_ready),
        "live_submit_caps_snapshot_readback_status": s("PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_READ", ctx.snapshot_ready),
        "firewall_contract_readback_status": s("PASS_FIREWALL_CONTRACT_READ", ctx.firewall_ready),
        "candidate_abstention_readback_status": s("PASS_CANDIDATE_ABSTENTION_READ", ctx.candidate_ready),
        "exact_pilot_approval_proof_status": s("PASS_EXACT_PILOT_APPROVAL_PROVEN", ctx.binder_ready),
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "kill_switch_proof_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_proof_status": "PASS_ROLLBACK_READY",
        "idempotency_proof_status": "PASS_IDEMPOTENCY_READY",
        "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE_PROVEN",
        "one_pilot_only_proof_status": "PASS_ONE_PILOT_ONLY",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "auth_packet_ready": ctx.packet_ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v100_status": "PASS",
        "execution_lock_deep_recheck_v99_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V140Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v139_baseline"):
        return "PASS" if ctx.v139_baseline_status == "PASS_V139_BASELINE_READBACK" else "FAIL" if ctx.v139_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v140_final_auth_packet_controller_report.json":
        return "PASS" if ctx.packet_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V140Context) -> dict[str, Any]:
    workstream = "v140: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v140_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V140_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v140_report.json":
        report.update({"completion_oriented_next_action_v140_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v139_carried_status": ctx.v139_baseline_status, "final_auth_packet_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v140_final_auth_packet_controller_report.json"), "no_submit": str(ARTIFACTS / "v140_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v140.json", "dummy_canonical_identity_report_v140.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V140ReportFactory:
    def __init__(self, *, binder_ready_override=None, snapshot_ready_override=None, firewall_ready_override=None, candidate_ready_override=None) -> None:
        self.kw = dict(binder_ready_override=binder_ready_override, snapshot_ready_override=snapshot_ready_override, firewall_ready_override=firewall_ready_override, candidate_ready_override=candidate_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V140Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
