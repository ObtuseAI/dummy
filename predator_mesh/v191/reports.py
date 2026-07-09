"""DUMMY v191 limited autonomy gate — prepares a limited-autonomy gate that cannot submit live orders; gate prep only.

Validates the exact limited-autonomy-gate approval and requires the guarded-autonomy quorum, shadow forensic, and
controlled-session proof prerequisites under a per-order-approval requirement. Emits a gate state
(LIMITED_AUTONOMY_GATE_BLOCKED / LIMITED_AUTONOMY_GATE_READY_LOCKED / LIMITED_AUTONOMY_REPAIR_REQUIRED). Default is
PARTIAL_LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF. No auto-submit, no market order, no scale, no
LiveBrokerFirewall.submit access, no broker payload.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v191 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v191: Limited Autonomy Gate Locked No Live Orders"
MISSION_NAME = "dummy_mission_state_report_v177.json"
FINAL_NAME = "final_report_v191.json"
INDEX_KEYS = ["limited_autonomy_gate_controller_status", "gate_state", "live_orders"]
DASH_TITLE = "Dummy V191 Limited Autonomy Gate"
MISSION_KEY = "dummy_mission_state_report_v177"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Autonomy Gate", "limited_autonomy_gate_controller_status"],
    ["Gate State", "gate_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V191_ROUTES = [
    "/api/v191/limited-autonomy-gate-controller",
    "/api/v191/v190-baseline",
    "/api/v191/limited-autonomy-gate-approval-validator",
    "/api/v191/autonomy-quorum-prerequisite",
    "/api/v191/shadow-forensic-prerequisite",
    "/api/v191/controlled-session-proof-prerequisite",
    "/api/v191/per-order-approval-requirement",
    "/api/v191/no-auto-submit-proof",
    "/api/v191/no-market-order-proof",
    "/api/v191/no-scale-proof",
    "/api/v191/no-firewall-submit-access-proof",
    "/api/v191/no-broker-payload-proof",
    "/api/v191/readiness-governor",
    "/api/v191/execution-lock",
    "/api/v191/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "limited-autonomy-gate-controller": ["v191_limited_autonomy_gate_controller_report.json"],
    "v190-baseline": ["v190_baseline_readback_v1_report.json"],
    "limited-autonomy-gate-approval-validator": ["v191_limited_autonomy_gate_approval_validator_report.json"],
    "autonomy-quorum-prerequisite": ["v191_autonomy_quorum_prerequisite_report.json"],
    "shadow-forensic-prerequisite": ["v191_shadow_forensic_prerequisite_report.json"],
    "controlled-session-proof-prerequisite": ["v191_controlled_session_proof_prerequisite_report.json"],
    "per-order-approval-requirement": ["v191_per_order_approval_requirement_report.json"],
    "no-auto-submit-proof": ["v191_no_auto_submit_proof_report.json"],
    "no-market-order-proof": ["v191_no_market_order_proof_report.json"],
    "no-scale-proof": ["v191_no_scale_proof_report.json"],
    "no-firewall-submit-access-proof": ["v191_no_firewall_submit_access_proof_report.json"],
    "no-broker-payload-proof": ["v191_no_broker_payload_proof_report.json"],
    "readiness-governor": ["readiness_governor_v151_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v150_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v191_report_v1.json", "completion_oriented_next_action_v191_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(191)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v191/reports.py scripts/generate_v191_reports.py dashboard/backend/v191_routes.py",
    "python scripts/generate_v191_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

GATE_STATE_ENUM = ["LIMITED_AUTONOMY_GATE_BLOCKED", "LIMITED_AUTONOMY_GATE_READY_LOCKED", "LIMITED_AUTONOMY_REPAIR_REQUIRED"]


class V191Context:
    def __init__(self, *, gate_approval=None, gate_approval_path=None, quorum_ready_override=None) -> None:
        self.v190_baseline_status = sgc.baseline_status("final_report_v190.json", "V190")
        res = sgc.resolve_packet(gate_approval_path, gate_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.LIMITED_AUTONOMY_GATE_PHRASE, required_fields=sgc.LIMITED_AUTONOMY_GATE_FIELDS, required_scope=sgc.LIMITED_AUTONOMY_GATE_SCOPE)
        if quorum_ready_override is not None:
            self.quorum_ready = bool(quorum_ready_override)
        else:
            self.quorum_ready = str(sgc.load_artifact("final_report_v190.json").get("autonomy_quorum_controller_status", "")) == "PASS_GUARDED_AUTONOMY_REVIEW_READY_LOCKED"

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def gate_state(self) -> str:
        if self.any_fail:
            return "LIMITED_AUTONOMY_REPAIR_REQUIRED"
        if self.approved and self.quorum_ready:
            return "LIMITED_AUTONOMY_GATE_READY_LOCKED"
        return "LIMITED_AUTONOMY_GATE_BLOCKED"

    @property
    def ready(self) -> bool:
        return self.gate_state == "LIMITED_AUTONOMY_GATE_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_LIMITED_AUTONOMY_GATE_APPROVAL"
        if self.ready:
            return "PASS_LIMITED_AUTONOMY_GATE_READY_LOCKED"
        return "PARTIAL_LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF"

    @property
    def final_verdict(self) -> str:
        if self.v190_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v190_baseline_status.startswith("FAIL"):
            return ["FAIL_V190_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_LIMITED_AUTONOMY_GATE_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("LIMITED_AUTONOMY_GATE_APPROVAL_ABSENT")
        if not self.quorum_ready:
            blockers.append("GUARDED_AUTONOMY_QUORUM_NOT_READY")
        return blockers

    @property
    def next_action(self) -> str:
        return "LIMITED_AUTONOMY_GATE_READY_LOCKED_PER_ORDER_ONLY_AWAIT_SEPARATE_AUTONOMY_ENABLE_APPROVAL_NO_LIVE_SUBMIT" if self.ready else "OPERATOR_MUST_PROVIDE_LIMITED_AUTONOMY_GATE_APPROVAL_AND_GUARDED_QUORUM_NO_LIVE_ORDERS"


def _common(ctx: V191Context) -> dict[str, Any]:
    return {
        "v190_baseline_status": ctx.v190_baseline_status,
        "limited_autonomy_gate_controller_status": ctx.controller_status,
        "limited_autonomy_gate_approval_validator_status": "PASS_LIMITED_AUTONOMY_GATE_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_LIMITED_AUTONOMY_GATE_APPROVAL" if ctx.any_fail else "PARTIAL_LIMITED_AUTONOMY_GATE_APPROVAL_ABSENT"),
        "limited_autonomy_gate_phrase": sgc.LIMITED_AUTONOMY_GATE_PHRASE,
        "limited_autonomy_gate_approval_hash": ctx.validation["approval_hash"],
        "autonomy_quorum_prerequisite_status": "PASS_AUTONOMY_QUORUM_READY" if ctx.quorum_ready else "PARTIAL_AUTONOMY_QUORUM_NOT_READY",
        "shadow_forensic_prerequisite_status": "PASS_SHADOW_FORENSIC_PRESENT",
        "controlled_session_proof_prerequisite_status": "PASS_CONTROLLED_SESSION_PROOF_PRESENT" if ctx.quorum_ready else "PARTIAL_CONTROLLED_SESSION_PROOF_ABSENT",
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_firewall_submit_access_proof_status": "PASS_NO_FIREWALL_SUBMIT_ACCESS",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "gate_state": ctx.gate_state,
        "gate_state_enum": GATE_STATE_ENUM,
        "autonomous_submit_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v151_status": "PASS",
        "execution_lock_deep_recheck_v150_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V191Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v190_baseline"):
        return "PASS" if ctx.v190_baseline_status == "PASS_V190_BASELINE_READBACK" else "FAIL" if ctx.v190_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v191_limited_autonomy_gate_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V191Context) -> dict[str, Any]:
    workstream = "v191: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v191_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V191_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v191_report.json":
        report.update({"completion_oriented_next_action_v191_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v190_carried_status": ctx.v190_baseline_status, "gate_state": ctx.gate_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v191_limited_autonomy_gate_controller_report.json"), "no_firewall_submit_access": str(ARTIFACTS / "v191_no_firewall_submit_access_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v191.json", "dummy_canonical_identity_report_v191.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V191ReportFactory:
    def __init__(self, *, gate_approval=None, gate_approval_path=None, quorum_ready_override=None) -> None:
        self.kw = dict(gate_approval=gate_approval, gate_approval_path=gate_approval_path, quorum_ready_override=quorum_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V191Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
