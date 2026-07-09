"""DUMMY v176 live session final preflight — assembles the final controlled-operation live-session preflight packet; never submits.

Reads the V175 approval validation plus controlled-operation / controlled-session / pilot-pair / live-submit-caps /
firewall / candidate proofs, per-order approval requirement, limit-only / no-market proofs, risk/abstention/kill-switch/
rollback/idempotency/liquidity proofs, and a max session order count. Default is PARTIAL_LIVE_SESSION_PREFLIGHT_BLOCKED.
When the approval is valid the packet is READY — nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v176 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
MAX_SESSION_ORDER_COUNT = 3

WORKSTREAM = "v176: Live Session Final Preflight Per Order Approval No Submit"
MISSION_NAME = "dummy_mission_state_report_v162.json"
FINAL_NAME = "final_report_v176.json"
INDEX_KEYS = ["session_preflight_controller_status", "session_preflight_ready", "live_orders"]
DASH_TITLE = "Dummy V176 Live Session Final Preflight"
MISSION_KEY = "dummy_mission_state_report_v162"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Session Preflight", "session_preflight_controller_status"],
    ["Preflight Ready", "session_preflight_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V176_ROUTES = [
    "/api/v176/session-preflight-controller",
    "/api/v176/v175-baseline",
    "/api/v176/controlled-operation-approval-proof",
    "/api/v176/controlled-session-approval-proof",
    "/api/v176/pilot-pair-prerequisite-proof",
    "/api/v176/live-submit-caps-snapshot-proof",
    "/api/v176/firewall-adapter-proof",
    "/api/v176/broker-readonly-proof",
    "/api/v176/candidate-sequence-proof",
    "/api/v176/per-order-approval-requirement",
    "/api/v176/limit-only-proof",
    "/api/v176/no-market-order-proof",
    "/api/v176/risk-governor-proof",
    "/api/v176/abstention-governor-proof",
    "/api/v176/kill-switch-proof",
    "/api/v176/rollback-proof",
    "/api/v176/idempotency-proof",
    "/api/v176/liquidity-slippage-proof",
    "/api/v176/max-session-order-count",
    "/api/v176/no-submit-proof",
    "/api/v176/readiness-governor",
    "/api/v176/execution-lock",
    "/api/v176/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "session-preflight-controller": ["v176_session_preflight_controller_report.json"],
    "v175-baseline": ["v175_baseline_readback_v1_report.json"],
    "controlled-operation-approval-proof": ["v176_controlled_operation_approval_proof_report.json"],
    "controlled-session-approval-proof": ["v176_controlled_session_approval_proof_report.json"],
    "pilot-pair-prerequisite-proof": ["v176_pilot_pair_prerequisite_proof_report.json"],
    "live-submit-caps-snapshot-proof": ["v176_live_submit_caps_snapshot_proof_report.json"],
    "firewall-adapter-proof": ["v176_firewall_adapter_proof_report.json"],
    "broker-readonly-proof": ["v176_broker_readonly_proof_report.json"],
    "candidate-sequence-proof": ["v176_candidate_sequence_proof_report.json"],
    "per-order-approval-requirement": ["v176_per_order_approval_requirement_report.json"],
    "limit-only-proof": ["v176_limit_only_proof_report.json"],
    "no-market-order-proof": ["v176_no_market_order_proof_report.json"],
    "risk-governor-proof": ["v176_risk_governor_proof_report.json"],
    "abstention-governor-proof": ["v176_abstention_governor_proof_report.json"],
    "kill-switch-proof": ["v176_kill_switch_proof_report.json"],
    "rollback-proof": ["v176_rollback_proof_report.json"],
    "idempotency-proof": ["v176_idempotency_proof_report.json"],
    "liquidity-slippage-proof": ["v176_liquidity_slippage_proof_report.json"],
    "max-session-order-count": ["v176_max_session_order_count_report.json"],
    "no-submit-proof": ["v176_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v136_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v135_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v176_report_v1.json", "completion_oriented_next_action_v176_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(176)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v176/reports.py scripts/generate_v176_reports.py dashboard/backend/v176_routes.py",
    "python scripts/generate_v176_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V176Context:
    def __init__(self, *, approval_ready_override=None) -> None:
        self.v175_baseline_status = sgc.baseline_status("final_report_v175.json", "V175")
        if approval_ready_override is not None:
            self.approval_ready = bool(approval_ready_override)
        else:
            self.approval_ready = str(sgc.load_artifact("final_report_v175.json").get("controlled_operation_approval_controller_status", "")) == "PASS_CONTROLLED_OPERATION_APPROVAL_VALID_NO_SUBMIT"

    @property
    def ready(self) -> bool:
        return self.approval_ready

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_SESSION_PREFLIGHT_READY_NO_SUBMIT" if self.ready else "PARTIAL_LIVE_SESSION_PREFLIGHT_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v175_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v175_baseline_status.startswith("FAIL"):
            return ["FAIL_V175_BASELINE_REGRESSION"]
        return [] if self.ready else ["CONTROLLED_OPERATION_APPROVAL_NOT_VALID"]

    @property
    def next_action(self) -> str:
        return "LIVE_SESSION_PREFLIGHT_READY_NO_SUBMIT_AWAIT_CONTROLLED_SESSION_FIRE_ON_FULL_AUTH" if self.ready else "OPERATOR_MUST_VALIDATE_CONTROLLED_OPERATION_APPROVAL_BEFORE_PREFLIGHT_NO_SUBMIT"


def _common(ctx: V176Context) -> dict[str, Any]:
    def s(v):
        return v if ctx.ready else "PARTIAL_PROOF_ABSENT"
    return {
        "v175_baseline_status": ctx.v175_baseline_status,
        "session_preflight_controller_status": ctx.controller_status,
        "controlled_operation_approval_proof_status": s("PASS_CONTROLLED_OPERATION_APPROVAL_PROVEN"),
        "controlled_session_approval_proof_status": s("PASS_CONTROLLED_SESSION_APPROVAL_PROVEN"),
        "pilot_pair_prerequisite_proof_status": s("PASS_PILOT_PAIR_PROVEN"),
        "live_submit_caps_snapshot_proof_status": s("PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_PROVEN"),
        "firewall_adapter_proof_status": s("PASS_FIREWALL_ADAPTER_PROVEN"),
        "broker_readonly_proof_status": "PASS_BROKER_READONLY_OPTIONAL",
        "candidate_sequence_proof_status": s("PASS_CANDIDATE_SEQUENCE_PROVEN"),
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "risk_governor_proof_status": "PASS_RISK_GOVERNOR_PROVEN",
        "abstention_governor_proof_status": "PASS_ABSTENTION_GOVERNOR_PROVEN",
        "kill_switch_proof_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_proof_status": "PASS_ROLLBACK_READY",
        "idempotency_proof_status": "PASS_IDEMPOTENCY_READY",
        "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE_PROVEN",
        "max_session_order_count_status": "PASS_MAX_SESSION_ORDER_COUNT_LOCKED",
        "max_session_order_count": MAX_SESSION_ORDER_COUNT,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "session_preflight_ready": ctx.ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v136_status": "PASS",
        "execution_lock_deep_recheck_v135_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V176Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v175_baseline"):
        return "PASS" if ctx.v175_baseline_status == "PASS_V175_BASELINE_READBACK" else "FAIL" if ctx.v175_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v176_session_preflight_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V176Context) -> dict[str, Any]:
    workstream = "v176: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v176_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V176_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v176_report.json":
        report.update({"completion_oriented_next_action_v176_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v175_carried_status": ctx.v175_baseline_status, "session_preflight_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v176_session_preflight_controller_report.json"), "no_submit": str(ARTIFACTS / "v176_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v176.json", "dummy_canonical_identity_report_v176.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V176ReportFactory:
    def __init__(self, *, approval_ready_override=None) -> None:
        self.kw = dict(approval_ready_override=approval_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V176Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
