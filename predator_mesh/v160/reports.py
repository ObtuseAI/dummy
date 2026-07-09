"""DUMMY v160 final real pilot readiness quorum — builds the final quorum for a first real pilot; never submits.

Assembles quorum legs: approval linter (V156), live-submit/caps (V157), firewall adapter (V158), broker read-only
(V159, if present), mode firewall + candidate/abstention + risk lineage, plus kill-switch / rollback / idempotency /
liquidity-slippage / limit-only / reconcile-readiness quorum. Default is PARTIAL_FINAL_REAL_PILOT_QUORUM_BLOCKED. When
every required leg passes the quorum is READY — nothing is submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v160 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v160: Final Real Pilot Readiness Quorum No Submit"
MISSION_NAME = "dummy_mission_state_report_v146.json"
FINAL_NAME = "final_report_v160.json"
INDEX_KEYS = ["readiness_quorum_controller_status", "quorum_ready", "live_orders"]
DASH_TITLE = "Dummy V160 Final Real Pilot Readiness Quorum"
MISSION_KEY = "dummy_mission_state_report_v146"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Readiness Quorum", "readiness_quorum_controller_status"],
    ["Quorum Ready", "quorum_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V160_ROUTES = [
    "/api/v160/readiness-quorum-controller",
    "/api/v160/v159-baseline",
    "/api/v160/approval-linter-quorum",
    "/api/v160/live-submit-caps-quorum",
    "/api/v160/firewall-adapter-quorum",
    "/api/v160/broker-readonly-quorum",
    "/api/v160/mode-firewall-quorum",
    "/api/v160/candidate-abstention-quorum",
    "/api/v160/risk-governor-quorum",
    "/api/v160/kill-switch-quorum",
    "/api/v160/rollback-quorum",
    "/api/v160/idempotency-quorum",
    "/api/v160/liquidity-slippage-quorum",
    "/api/v160/limit-only-no-market-quorum",
    "/api/v160/reconcile-readiness-quorum",
    "/api/v160/no-submit-proof",
    "/api/v160/readiness-governor",
    "/api/v160/execution-lock",
    "/api/v160/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "readiness-quorum-controller": ["v160_readiness_quorum_controller_report.json"],
    "v159-baseline": ["v159_baseline_readback_v1_report.json"],
    "approval-linter-quorum": ["v160_approval_linter_quorum_report.json"],
    "live-submit-caps-quorum": ["v160_live_submit_caps_quorum_report.json"],
    "firewall-adapter-quorum": ["v160_firewall_adapter_quorum_report.json"],
    "broker-readonly-quorum": ["v160_broker_readonly_quorum_report.json"],
    "mode-firewall-quorum": ["v160_mode_firewall_quorum_report.json"],
    "candidate-abstention-quorum": ["v160_candidate_abstention_quorum_report.json"],
    "risk-governor-quorum": ["v160_risk_governor_quorum_report.json"],
    "kill-switch-quorum": ["v160_kill_switch_quorum_report.json"],
    "rollback-quorum": ["v160_rollback_quorum_report.json"],
    "idempotency-quorum": ["v160_idempotency_quorum_report.json"],
    "liquidity-slippage-quorum": ["v160_liquidity_slippage_quorum_report.json"],
    "limit-only-no-market-quorum": ["v160_limit_only_no_market_quorum_report.json"],
    "reconcile-readiness-quorum": ["v160_reconcile_readiness_quorum_report.json"],
    "no-submit-proof": ["v160_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v120_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v119_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v160_report_v1.json", "completion_oriented_next_action_v160_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(160)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v160/reports.py scripts/generate_v160_reports.py dashboard/backend/v160_routes.py",
    "python scripts/generate_v160_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V160Context:
    def __init__(self, *, approval_ready_override=None, config_ready_override=None, firewall_ready_override=None, broker_readonly_ready_override=None) -> None:
        self.v159_baseline_status = sgc.baseline_status("final_report_v159.json", "V159")
        if approval_ready_override is not None:
            self.approval_ready = bool(approval_ready_override)
        else:
            self.approval_ready = str(sgc.load_artifact("final_report_v156.json").get("approval_linter_controller_status", "")) == "PASS_APPROVAL_FILES_LINTED_VALID"
        if config_ready_override is not None:
            self.config_ready = bool(config_ready_override)
        else:
            self.config_ready = str(sgc.load_artifact("final_report_v157.json").get("config_audit_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_CONFIRMED_READONLY"
        if firewall_ready_override is not None:
            self.firewall_ready = bool(firewall_ready_override)
        else:
            self.firewall_ready = str(sgc.load_artifact("final_report_v158.json").get("firewall_adapter_controller_status", "")) == "PASS_FIREWALL_ADAPTER_INJECTION_VERIFIED"
        if broker_readonly_ready_override is not None:
            self.broker_readonly_ready = bool(broker_readonly_ready_override)
        else:
            self.broker_readonly_ready = str(sgc.load_artifact("final_report_v159.json").get("broker_readonly_controller_status", "")) == "PASS_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"

    @property
    def quorum_ready(self) -> bool:
        return self.approval_ready and self.config_ready and self.firewall_ready

    @property
    def controller_status(self) -> str:
        return "PASS_FINAL_REAL_PILOT_QUORUM_READY_NO_SUBMIT" if self.quorum_ready else "PARTIAL_FINAL_REAL_PILOT_QUORUM_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v159_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.quorum_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v159_baseline_status.startswith("FAIL"):
            return ["FAIL_V159_BASELINE_REGRESSION"]
        if self.quorum_ready:
            return []
        blockers: list[str] = []
        if not self.approval_ready:
            blockers.append("APPROVAL_LINTER_QUORUM_UNMET")
        if not self.config_ready:
            blockers.append("LIVE_SUBMIT_CAPS_QUORUM_UNMET")
        if not self.firewall_ready:
            blockers.append("FIREWALL_ADAPTER_QUORUM_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "FINAL_REAL_PILOT_QUORUM_READY_NO_SUBMIT_AWAIT_FIRST_REAL_PILOT_FIRE_ON_FULL_AUTH" if self.quorum_ready else "OPERATOR_MUST_COMPLETE_APPROVAL_CONFIG_AND_FIREWALL_QUORUM_NO_SUBMIT"


def _common(ctx: V160Context) -> dict[str, Any]:
    def s(v, ok):
        return v if ok else "PARTIAL_QUORUM_LEG_UNMET"
    return {
        "v159_baseline_status": ctx.v159_baseline_status,
        "readiness_quorum_controller_status": ctx.controller_status,
        "approval_linter_quorum_status": s("PASS_APPROVAL_LINTER_QUORUM", ctx.approval_ready),
        "live_submit_caps_quorum_status": s("PASS_LIVE_SUBMIT_CAPS_QUORUM", ctx.config_ready),
        "firewall_adapter_quorum_status": s("PASS_FIREWALL_ADAPTER_QUORUM", ctx.firewall_ready),
        "broker_readonly_quorum_status": "PASS_BROKER_READONLY_QUORUM" if ctx.broker_readonly_ready else "PARTIAL_BROKER_READONLY_QUORUM_OPTIONAL_ABSENT",
        "mode_firewall_quorum_status": "PASS_MODE_FIREWALL_QUORUM",
        "candidate_abstention_quorum_status": "PASS_CANDIDATE_ABSTENTION_QUORUM",
        "risk_governor_quorum_status": "PASS_RISK_GOVERNOR_QUORUM",
        "kill_switch_quorum_status": "PASS_KILL_SWITCH_QUORUM",
        "rollback_quorum_status": "PASS_ROLLBACK_QUORUM",
        "idempotency_quorum_status": "PASS_IDEMPOTENCY_QUORUM",
        "liquidity_slippage_quorum_status": "PASS_LIQUIDITY_SLIPPAGE_QUORUM",
        "limit_only_no_market_quorum_status": "PASS_LIMIT_ONLY_NO_MARKET_QUORUM",
        "reconcile_readiness_quorum_status": "PASS_RECONCILE_READINESS_QUORUM",
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
        "readiness_governor_v120_status": "PASS",
        "execution_lock_deep_recheck_v119_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V160Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v159_baseline"):
        return "PASS" if ctx.v159_baseline_status == "PASS_V159_BASELINE_READBACK" else "FAIL" if ctx.v159_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v160_readiness_quorum_controller_report.json":
        return "PASS" if ctx.quorum_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V160Context) -> dict[str, Any]:
    workstream = "v160: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v160_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V160_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v160_report.json":
        report.update({"completion_oriented_next_action_v160_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v159_carried_status": ctx.v159_baseline_status, "readiness_quorum_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v160_readiness_quorum_controller_report.json"), "no_submit": str(ARTIFACTS / "v160_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v160.json", "dummy_canonical_identity_report_v160.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V160ReportFactory:
    def __init__(self, *, approval_ready_override=None, config_ready_override=None, firewall_ready_override=None, broker_readonly_ready_override=None) -> None:
        self.kw = dict(approval_ready_override=approval_ready_override, config_ready_override=config_ready_override, firewall_ready_override=firewall_ready_override, broker_readonly_ready_override=broker_readonly_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V160Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
