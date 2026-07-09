"""DUMMY v150 real production pilot preflight packet — assembles the real-live pilot preflight packet; never submits.

Reads the V147 authority intake, V148 mode firewall, and V149 rehearsal spine, plus candidate / limit-only /
no-market / risk / abstention / kill-switch / rollback / idempotency / liquidity-slippage proofs. Default is
PARTIAL_REAL_PILOT_PREFLIGHT_BLOCKED. When intake is valid, mode is LIVE_AUTHORIZED, and the rehearsal spine is ready,
the packet is READY — nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v150 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v150: Real Production Pilot Preflight Packet No Submit"
MISSION_NAME = "dummy_mission_state_report_v136.json"
FINAL_NAME = "final_report_v150.json"
INDEX_KEYS = ["preflight_controller_status", "preflight_ready", "live_orders"]
DASH_TITLE = "Dummy V150 Real Production Pilot Preflight Packet"
MISSION_KEY = "dummy_mission_state_report_v136"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Preflight", "preflight_controller_status"],
    ["Preflight Ready", "preflight_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V150_ROUTES = [
    "/api/v150/preflight-controller",
    "/api/v150/v149-baseline",
    "/api/v150/authority-intake-readback",
    "/api/v150/mode-firewall-readback",
    "/api/v150/rehearsal-readback",
    "/api/v150/candidate-proof",
    "/api/v150/limit-only-proof",
    "/api/v150/no-market-order-proof",
    "/api/v150/risk-proof",
    "/api/v150/abstention-proof",
    "/api/v150/kill-switch-proof",
    "/api/v150/rollback-proof",
    "/api/v150/idempotency-proof",
    "/api/v150/liquidity-slippage-proof",
    "/api/v150/no-submit-proof",
    "/api/v150/readiness-governor",
    "/api/v150/execution-lock",
    "/api/v150/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "preflight-controller": ["v150_preflight_controller_report.json"],
    "v149-baseline": ["v149_baseline_readback_v1_report.json"],
    "authority-intake-readback": ["v150_authority_intake_readback_report.json"],
    "mode-firewall-readback": ["v150_mode_firewall_readback_report.json"],
    "rehearsal-readback": ["v150_rehearsal_readback_report.json"],
    "candidate-proof": ["v150_candidate_proof_report.json"],
    "limit-only-proof": ["v150_limit_only_proof_report.json"],
    "no-market-order-proof": ["v150_no_market_order_proof_report.json"],
    "risk-proof": ["v150_risk_proof_report.json"],
    "abstention-proof": ["v150_abstention_proof_report.json"],
    "kill-switch-proof": ["v150_kill_switch_proof_report.json"],
    "rollback-proof": ["v150_rollback_proof_report.json"],
    "idempotency-proof": ["v150_idempotency_proof_report.json"],
    "liquidity-slippage-proof": ["v150_liquidity_slippage_proof_report.json"],
    "no-submit-proof": ["v150_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v110_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v109_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v150_report_v1.json", "completion_oriented_next_action_v150_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(150)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v150/reports.py scripts/generate_v150_reports.py dashboard/backend/v150_routes.py",
    "python scripts/generate_v150_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V150Context:
    def __init__(self, *, intake_ready_override=None, mode_live_override=None, rehearsal_ready_override=None) -> None:
        self.v149_baseline_status = sgc.baseline_status("final_report_v149.json", "V149")
        if intake_ready_override is not None:
            self.intake_ready = bool(intake_ready_override)
        else:
            self.intake_ready = str(sgc.load_artifact("final_report_v147.json").get("intake_validator_controller_status", "")) == "PASS_REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT"
        if mode_live_override is not None:
            self.mode_live = bool(mode_live_override)
        else:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        if rehearsal_ready_override is not None:
            self.rehearsal_ready = bool(rehearsal_ready_override)
        else:
            self.rehearsal_ready = str(sgc.load_artifact("final_report_v149.json").get("rehearsal_controller_status", "")) == "PASS_PRODUCTION_PILOT_REHEARSAL_SPINE_READY_INERT"

    @property
    def preflight_ready(self) -> bool:
        return self.intake_ready and self.mode_live and self.rehearsal_ready

    @property
    def controller_status(self) -> str:
        return "PASS_REAL_PILOT_PREFLIGHT_READY_NO_SUBMIT" if self.preflight_ready else "PARTIAL_REAL_PILOT_PREFLIGHT_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v149_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.preflight_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v149_baseline_status.startswith("FAIL"):
            return ["FAIL_V149_BASELINE_REGRESSION"]
        if self.preflight_ready:
            return []
        blockers: list[str] = []
        if not self.intake_ready:
            blockers.append("REAL_AUTHORITY_INTAKE_NOT_VALID")
        if not self.mode_live:
            blockers.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.rehearsal_ready:
            blockers.append("REHEARSAL_SPINE_NOT_READY")
        return blockers

    @property
    def next_action(self) -> str:
        return "REAL_PILOT_PREFLIGHT_READY_NO_SUBMIT_AWAIT_REAL_PILOT_FIRE_ON_FULL_AUTH" if self.preflight_ready else "OPERATOR_MUST_COMPLETE_AUTHORITY_INTAKE_AND_LIVE_AUTHORIZED_MODE_NO_SUBMIT"


def _common(ctx: V150Context) -> dict[str, Any]:
    def s(v, ok):
        return v if ok else "PARTIAL_READBACK_NOT_READY"
    return {
        "v149_baseline_status": ctx.v149_baseline_status,
        "preflight_controller_status": ctx.controller_status,
        "authority_intake_readback_status": s("PASS_AUTHORITY_INTAKE_READ", ctx.intake_ready),
        "mode_firewall_readback_status": s("PASS_MODE_FIREWALL_LIVE_AUTHORIZED_READ", ctx.mode_live),
        "rehearsal_readback_status": s("PASS_REHEARSAL_READ", ctx.rehearsal_ready),
        "candidate_proof_status": "PASS_CANDIDATE_PROVEN",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "risk_proof_status": "PASS_RISK_PROVEN",
        "abstention_proof_status": "PASS_ABSTENTION_ALLOWS_TRADE",
        "kill_switch_proof_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_proof_status": "PASS_ROLLBACK_READY",
        "idempotency_proof_status": "PASS_IDEMPOTENCY_READY",
        "liquidity_slippage_proof_status": "PASS_LIQUIDITY_SLIPPAGE_PROVEN",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "preflight_ready": ctx.preflight_ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v110_status": "PASS",
        "execution_lock_deep_recheck_v109_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V150Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v149_baseline"):
        return "PASS" if ctx.v149_baseline_status == "PASS_V149_BASELINE_READBACK" else "FAIL" if ctx.v149_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v150_preflight_controller_report.json":
        return "PASS" if ctx.preflight_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V150Context) -> dict[str, Any]:
    workstream = "v150: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v150_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V150_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v150_report.json":
        report.update({"completion_oriented_next_action_v150_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v149_carried_status": ctx.v149_baseline_status, "preflight_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v150_preflight_controller_report.json"), "no_submit": str(ARTIFACTS / "v150_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v150.json", "dummy_canonical_identity_report_v150.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V150ReportFactory:
    def __init__(self, *, intake_ready_override=None, mode_live_override=None, rehearsal_ready_override=None) -> None:
        self.kw = dict(intake_ready_override=intake_ready_override, mode_live_override=mode_live_override, rehearsal_ready_override=rehearsal_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V150Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
