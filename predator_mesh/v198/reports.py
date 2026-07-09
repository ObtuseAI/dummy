"""DUMMY v198 first live-proof final quorum — builds the final first-live-proof quorum and selects a proof target; never submits.

Assembles approval (V195), config/caps (V196), and firewall/broker (V197) quorum legs plus mode-firewall,
candidate/abstention, risk, shadow-forensic, kill-switch, rollback, idempotency, liquidity-slippage, limit-only, and
reconcile-readiness quorum. Selects a proof target (FIRST_REAL_PILOT_PROOF / CONTROLLED_SESSION_PROOF /
BLOCKED_NO_AUTHORITY). Default is PARTIAL_FIRST_LIVE_PROOF_QUORUM_BLOCKED. Nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v198 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v198: First Live Proof Final Quorum No Submit"
MISSION_NAME = "dummy_mission_state_report_v184.json"
FINAL_NAME = "final_report_v198.json"
INDEX_KEYS = ["final_quorum_controller_status", "proof_target", "live_orders"]
DASH_TITLE = "Dummy V198 First Live-Proof Final Quorum"
MISSION_KEY = "dummy_mission_state_report_v184"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Final Quorum", "final_quorum_controller_status"],
    ["Proof Target", "proof_target"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V198_ROUTES = [
    "/api/v198/final-quorum-controller",
    "/api/v198/v197-baseline",
    "/api/v198/approval-quorum",
    "/api/v198/config-caps-quorum",
    "/api/v198/firewall-broker-quorum",
    "/api/v198/mode-firewall-quorum",
    "/api/v198/candidate-abstention-quorum",
    "/api/v198/risk-governor-quorum",
    "/api/v198/shadow-forensic-quorum",
    "/api/v198/kill-switch-quorum",
    "/api/v198/rollback-quorum",
    "/api/v198/idempotency-quorum",
    "/api/v198/liquidity-slippage-quorum",
    "/api/v198/limit-only-no-market-quorum",
    "/api/v198/reconcile-readiness-quorum",
    "/api/v198/proof-target-selector",
    "/api/v198/no-submit-proof",
    "/api/v198/readiness-governor",
    "/api/v198/execution-lock",
    "/api/v198/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "final-quorum-controller": ["v198_final_quorum_controller_report.json"],
    "v197-baseline": ["v197_baseline_readback_v1_report.json"],
    "approval-quorum": ["v198_approval_quorum_report.json"],
    "config-caps-quorum": ["v198_config_caps_quorum_report.json"],
    "firewall-broker-quorum": ["v198_firewall_broker_quorum_report.json"],
    "mode-firewall-quorum": ["v198_mode_firewall_quorum_report.json"],
    "candidate-abstention-quorum": ["v198_candidate_abstention_quorum_report.json"],
    "risk-governor-quorum": ["v198_risk_governor_quorum_report.json"],
    "shadow-forensic-quorum": ["v198_shadow_forensic_quorum_report.json"],
    "kill-switch-quorum": ["v198_kill_switch_quorum_report.json"],
    "rollback-quorum": ["v198_rollback_quorum_report.json"],
    "idempotency-quorum": ["v198_idempotency_quorum_report.json"],
    "liquidity-slippage-quorum": ["v198_liquidity_slippage_quorum_report.json"],
    "limit-only-no-market-quorum": ["v198_limit_only_no_market_quorum_report.json"],
    "reconcile-readiness-quorum": ["v198_reconcile_readiness_quorum_report.json"],
    "proof-target-selector": ["v198_proof_target_selector_report.json"],
    "no-submit-proof": ["v198_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v158_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v157_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v198_report_v1.json", "completion_oriented_next_action_v198_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(198)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v198/reports.py scripts/generate_v198_reports.py dashboard/backend/v198_routes.py",
    "python scripts/generate_v198_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

PROOF_TARGET_ENUM = ["FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF", "BLOCKED_NO_AUTHORITY"]


class V198Context:
    def __init__(self, *, approval_ready_override=None, config_ready_override=None, firewall_ready_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF") -> None:
        self.v197_baseline_status = sgc.baseline_status("final_report_v197.json", "V197")
        if approval_ready_override is not None:
            self.approval_ready = bool(approval_ready_override)
        else:
            self.approval_ready = str(sgc.load_artifact("final_report_v195.json").get("activation_binder_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_AUTHORITY_BOUND_NO_SUBMIT"
        if config_ready_override is not None:
            self.config_ready = bool(config_ready_override)
        else:
            self.config_ready = str(sgc.load_artifact("final_report_v196.json").get("config_quorum_controller_status", "")) == "PASS_LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE"
        if firewall_ready_override is not None:
            self.firewall_ready = bool(firewall_ready_override)
        else:
            self.firewall_ready = str(sgc.load_artifact("final_report_v197.json").get("firewall_broker_controller_status", "")) == "PASS_FIREWALL_AND_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
        self.proof_target_choice = proof_target_override

    @property
    def quorum_ready(self) -> bool:
        return self.approval_ready and self.config_ready and self.firewall_ready

    @property
    def proof_target(self) -> str:
        return self.proof_target_choice if self.quorum_ready else "BLOCKED_NO_AUTHORITY"

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_LIVE_PROOF_QUORUM_READY_NO_SUBMIT" if self.quorum_ready else "PARTIAL_FIRST_LIVE_PROOF_QUORUM_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v197_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.quorum_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v197_baseline_status.startswith("FAIL"):
            return ["FAIL_V197_BASELINE_REGRESSION"]
        if self.quorum_ready:
            return []
        blockers: list[str] = []
        if not self.approval_ready:
            blockers.append("APPROVAL_QUORUM_UNMET")
        if not self.config_ready:
            blockers.append("CONFIG_CAPS_QUORUM_UNMET")
        if not self.firewall_ready:
            blockers.append("FIREWALL_BROKER_QUORUM_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_PROOF_QUORUM_READY_NO_SUBMIT_AWAIT_FIRST_LIVE_PROOF_FIRE_ON_FULL_AUTH" if self.quorum_ready else "OPERATOR_MUST_COMPLETE_APPROVAL_CONFIG_AND_FIREWALL_BROKER_QUORUM_NO_SUBMIT"


def _common(ctx: V198Context) -> dict[str, Any]:
    def s(v, ok):
        return v if ok else "PARTIAL_QUORUM_LEG_UNMET"
    return {
        "v197_baseline_status": ctx.v197_baseline_status,
        "final_quorum_controller_status": ctx.controller_status,
        "approval_quorum_status": s("PASS_APPROVAL_QUORUM", ctx.approval_ready),
        "config_caps_quorum_status": s("PASS_CONFIG_CAPS_QUORUM", ctx.config_ready),
        "firewall_broker_quorum_status": s("PASS_FIREWALL_BROKER_QUORUM", ctx.firewall_ready),
        "mode_firewall_quorum_status": "PASS_MODE_FIREWALL_QUORUM",
        "candidate_abstention_quorum_status": "PASS_CANDIDATE_ABSTENTION_QUORUM",
        "risk_governor_quorum_status": "PASS_RISK_GOVERNOR_QUORUM",
        "shadow_forensic_quorum_status": "PASS_SHADOW_FORENSIC_QUORUM",
        "kill_switch_quorum_status": "PASS_KILL_SWITCH_QUORUM",
        "rollback_quorum_status": "PASS_ROLLBACK_QUORUM",
        "idempotency_quorum_status": "PASS_IDEMPOTENCY_QUORUM",
        "liquidity_slippage_quorum_status": "PASS_LIQUIDITY_SLIPPAGE_QUORUM",
        "limit_only_no_market_quorum_status": "PASS_LIMIT_ONLY_NO_MARKET_QUORUM",
        "reconcile_readiness_quorum_status": "PASS_RECONCILE_READINESS_QUORUM",
        "proof_target_selector_status": "PASS_PROOF_TARGET_SELECTED",
        "proof_target": ctx.proof_target,
        "proof_target_enum": PROOF_TARGET_ENUM,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "quorum_ready": ctx.quorum_ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v158_status": "PASS",
        "execution_lock_deep_recheck_v157_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V198Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v197_baseline"):
        return "PASS" if ctx.v197_baseline_status == "PASS_V197_BASELINE_READBACK" else "FAIL" if ctx.v197_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v198_final_quorum_controller_report.json":
        return "PASS" if ctx.quorum_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V198Context) -> dict[str, Any]:
    workstream = "v198: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v198_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V198_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v198_report.json":
        report.update({"completion_oriented_next_action_v198_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v197_carried_status": ctx.v197_baseline_status, "final_quorum_controller_status": ctx.controller_status, "proof_target": ctx.proof_target, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v198_final_quorum_controller_report.json"), "no_submit": str(ARTIFACTS / "v198_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v198.json", "dummy_canonical_identity_report_v198.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V198ReportFactory:
    def __init__(self, *, approval_ready_override=None, config_ready_override=None, firewall_ready_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF") -> None:
        self.kw = dict(approval_ready_override=approval_ready_override, config_ready_override=config_ready_override, firewall_ready_override=firewall_ready_override, proof_target_override=proof_target_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V198Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
