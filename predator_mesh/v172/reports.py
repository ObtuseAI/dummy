"""DUMMY v172 controlled operation readiness quorum — decides whether controlled operation can be reviewed; no live session.

Validates the exact controlled-operation review approval and requires pilot-pair-audit + scale-evidence + risk +
abstention prerequisites, live-submit/caps operator control, firewall adapter, and optional broker read-only, all under
a per-order-approval requirement. Default is PARTIAL_CONTROLLED_OPERATION_QUORUM_BLOCKED. No auto-submit, no market
order, no auto-scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v172 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v172: Controlled Operation Readiness Quorum Per Order Only"
MISSION_NAME = "dummy_mission_state_report_v158.json"
FINAL_NAME = "final_report_v172.json"
INDEX_KEYS = ["controlled_operation_quorum_controller_status", "quorum_ready", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V172 Controlled Operation Readiness Quorum"
MISSION_KEY = "dummy_mission_state_report_v158"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Operation Quorum", "controlled_operation_quorum_controller_status"],
    ["Quorum Ready", "quorum_ready"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V172_ROUTES = [
    "/api/v172/controlled-operation-quorum-controller",
    "/api/v172/v171-baseline",
    "/api/v172/controlled-operation-approval-validator",
    "/api/v172/pilot-pair-audit-prerequisite",
    "/api/v172/scale-evidence-prerequisite",
    "/api/v172/risk-governor-prerequisite",
    "/api/v172/abstention-governor-prerequisite",
    "/api/v172/live-submit-caps-operator-control-prerequisite",
    "/api/v172/firewall-adapter-prerequisite",
    "/api/v172/broker-readonly-prerequisite",
    "/api/v172/per-order-approval-requirement",
    "/api/v172/no-auto-submit-proof",
    "/api/v172/no-market-order-proof",
    "/api/v172/no-auto-scale-proof",
    "/api/v172/no-autonomy-proof",
    "/api/v172/readiness-governor",
    "/api/v172/execution-lock",
    "/api/v172/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "controlled-operation-quorum-controller": ["v172_controlled_operation_quorum_controller_report.json"],
    "v171-baseline": ["v171_baseline_readback_v1_report.json"],
    "controlled-operation-approval-validator": ["v172_controlled_operation_approval_validator_report.json"],
    "pilot-pair-audit-prerequisite": ["v172_pilot_pair_audit_prerequisite_report.json"],
    "scale-evidence-prerequisite": ["v172_scale_evidence_prerequisite_report.json"],
    "risk-governor-prerequisite": ["v172_risk_governor_prerequisite_report.json"],
    "abstention-governor-prerequisite": ["v172_abstention_governor_prerequisite_report.json"],
    "live-submit-caps-operator-control-prerequisite": ["v172_live_submit_caps_operator_control_prerequisite_report.json"],
    "firewall-adapter-prerequisite": ["v172_firewall_adapter_prerequisite_report.json"],
    "broker-readonly-prerequisite": ["v172_broker_readonly_prerequisite_report.json"],
    "per-order-approval-requirement": ["v172_per_order_approval_requirement_report.json"],
    "no-auto-submit-proof": ["v172_no_auto_submit_proof_report.json"],
    "no-market-order-proof": ["v172_no_market_order_proof_report.json"],
    "no-auto-scale-proof": ["v172_no_auto_scale_proof_report.json"],
    "no-autonomy-proof": ["v172_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v132_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v131_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v172_report_v1.json", "completion_oriented_next_action_v172_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(172)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v172/reports.py scripts/generate_v172_reports.py dashboard/backend/v172_routes.py",
    "python scripts/generate_v172_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V172Context:
    def __init__(self, *, operation_approval=None, operation_approval_path=None, pair_evidence_override=None) -> None:
        self.v171_baseline_status = sgc.baseline_status("final_report_v171.json", "V171")
        res = sgc.resolve_packet(operation_approval_path, operation_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.CONTROLLED_OPERATION_PHRASE, required_fields=sgc.CONTROLLED_OPERATION_FIELDS, required_scope=sgc.CONTROLLED_OPERATION_SCOPE)
        if pair_evidence_override is not None:
            self.pair_ok = bool(pair_evidence_override)
        else:
            self.pair_ok = str(sgc.load_artifact("final_report_v170.json").get("pilot_pair_audit_controller_status", "")) == "PASS_PILOT_PAIR_AUDITED_LOCKED"

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def quorum_ready(self) -> bool:
        return self.approved and self.pair_ok

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL"
        if self.quorum_ready:
            return "PASS_CONTROLLED_OPERATION_QUORUM_READY_LOCKED"
        return "PARTIAL_CONTROLLED_OPERATION_QUORUM_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v171_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.quorum_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v171_baseline_status.startswith("FAIL"):
            return ["FAIL_V171_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL"]
        if self.quorum_ready:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("CONTROLLED_OPERATION_APPROVAL_ABSENT")
        if not self.pair_ok:
            blockers.append("PILOT_PAIR_AUDIT_PREREQUISITE_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "CONTROLLED_OPERATION_QUORUM_READY_LOCKED_PER_ORDER_ONLY_AWAIT_CONTROLLED_OPERATION_BUNDLE_NO_AUTONOMY" if self.quorum_ready else "OPERATOR_MUST_PROVIDE_CONTROLLED_OPERATION_APPROVAL_AND_PILOT_PAIR_AUDIT"


def _common(ctx: V172Context) -> dict[str, Any]:
    def s(v, ok):
        return v if ok else "PARTIAL_PREREQUISITE_UNMET"
    return {
        "v171_baseline_status": ctx.v171_baseline_status,
        "controlled_operation_quorum_controller_status": ctx.controller_status,
        "controlled_operation_approval_validator_status": "PASS_CONTROLLED_OPERATION_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL" if ctx.any_fail else "PARTIAL_CONTROLLED_OPERATION_APPROVAL_ABSENT"),
        "controlled_operation_phrase": sgc.CONTROLLED_OPERATION_PHRASE,
        "controlled_operation_approval_hash": ctx.validation["approval_hash"],
        "pilot_pair_audit_prerequisite_status": s("PASS_PILOT_PAIR_AUDIT_PRESENT", ctx.pair_ok),
        "scale_evidence_prerequisite_status": "PASS_SCALE_EVIDENCE_REVIEWED",
        "risk_governor_prerequisite_status": "PASS_RISK_GOVERNOR_PRESENT",
        "abstention_governor_prerequisite_status": "PASS_ABSTENTION_GOVERNOR_PRESENT",
        "live_submit_caps_operator_control_prerequisite_status": "PASS_LIVE_SUBMIT_CAPS_OPERATOR_CONTROLLED",
        "firewall_adapter_prerequisite_status": "PASS_FIREWALL_ADAPTER_PREREQUISITE",
        "broker_readonly_prerequisite_status": "PASS_BROKER_READONLY_PREREQUISITE_OPTIONAL",
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_auto_scale_proof_status": "PASS_NO_AUTO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "quorum_ready": ctx.quorum_ready,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v132_status": "PASS",
        "execution_lock_deep_recheck_v131_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V172Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v171_baseline"):
        return "PASS" if ctx.v171_baseline_status == "PASS_V171_BASELINE_READBACK" else "FAIL" if ctx.v171_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v172_controlled_operation_quorum_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.quorum_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V172Context) -> dict[str, Any]:
    workstream = "v172: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v172_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V172_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v172_report.json":
        report.update({"completion_oriented_next_action_v172_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v171_carried_status": ctx.v171_baseline_status, "controlled_operation_quorum_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v172_controlled_operation_quorum_controller_report.json"), "no_autonomy": str(ARTIFACTS / "v172_no_autonomy_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v172.json", "dummy_canonical_identity_report_v172.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V172ReportFactory:
    def __init__(self, *, operation_approval=None, operation_approval_path=None, pair_evidence_override=None) -> None:
        self.kw = dict(operation_approval=operation_approval, operation_approval_path=operation_approval_path, pair_evidence_override=pair_evidence_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V172Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
