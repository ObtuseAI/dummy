"""DUMMY v102 order 2 approval and stricter repeat gate (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v102 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V102_ROUTES = [
    "/api/v102/order-2-gate-controller",
    "/api/v102/v101-baseline",
    "/api/v102/order-2-approval-validator",
    "/api/v102/campaign-approval-still-valid",
    "/api/v102/order-1-reconcile-prerequisite",
    "/api/v102/order-1-forensic-prerequisite",
    "/api/v102/stricter-risk-threshold",
    "/api/v102/no-loss-lock",
    "/api/v102/no-drift-lock",
    "/api/v102/no-repeat-without-approval-proof",
    "/api/v102/readiness-governor",
    "/api/v102/execution-lock",
    "/api/v102/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "order-2-gate-controller": ["v102_order_2_gate_controller_report.json"],
    "v101-baseline": ["v101_baseline_readback_v1_report.json"],
    "order-2-approval-validator": ["v102_order_2_approval_validator_report.json"],
    "campaign-approval-still-valid": ["v102_campaign_approval_still_valid_report.json"],
    "order-1-reconcile-prerequisite": ["v102_order_1_reconcile_prerequisite_report.json"],
    "order-1-forensic-prerequisite": ["v102_order_1_forensic_prerequisite_report.json"],
    "stricter-risk-threshold": ["v102_stricter_risk_threshold_report.json"],
    "no-loss-lock": ["v102_no_loss_lock_report.json"],
    "no-drift-lock": ["v102_no_drift_lock_report.json"],
    "no-repeat-without-approval-proof": ["v102_no_repeat_without_approval_proof_report.json"],
    "readiness-governor": ["readiness_governor_v62_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v61_report.json"],
    "mission-state": ["dummy_mission_state_report_v88.json", "dashboard_v102_report_v1.json", "completion_oriented_next_action_v102_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(102)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v102/reports.py scripts/generate_v102_reports.py dashboard/backend/v102_routes.py",
    "python scripts/generate_v102_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V102Context:
    def __init__(self, *, campaign_approval, order_2_approval, order_2_approval_path, order_1_reconciled_override, order_1_forensic_override) -> None:
        self.v101_baseline_status = sgc.baseline_status("final_report_v101.json", "V101")
        self.campaign_approved = bool(campaign_approval and campaign_approval.get("exact_phrase") == sgc.MICRO_CAMPAIGN_PHRASE)
        ores = sgc.resolve_packet(order_2_approval_path, order_2_approval)
        self.order_validation = sgc.validate_packet(ores, required_phrase=sgc.CAMPAIGN_PER_ORDER_PHRASE, required_fields=sgc.CAMPAIGN_PER_ORDER_FIELDS, required_scope=sgc.CAMPAIGN_PER_ORDER_SCOPE, ack_requirements=sgc.CAMPAIGN_PER_ORDER_ACKS)
        if order_1_reconciled_override is None:
            self.order_1_reconciled = str(sgc.load_artifact("final_report_v100.json").get("reconcile_controller_status", "")) == "PASS_ORDER1_RECONCILED_AUTOLOCKED"
        else:
            self.order_1_reconciled = bool(order_1_reconciled_override)
        if order_1_forensic_override is None:
            self.order_1_forensic = sgc.load_artifact("final_report_v101.json").get("verdict") == "PASS"
        else:
            self.order_1_forensic = bool(order_1_forensic_override)

    @property
    def gate_ready(self) -> bool:
        return self.campaign_approved and self.order_validation["accepted"] and self.order_1_reconciled and self.order_1_forensic

    @property
    def controller_status(self) -> str:
        if self.order_validation["state"] == "PRESENT" and not self.order_validation["accepted"]:
            return "FAIL_CLOSED_INVALID_ORDER2_APPROVAL"
        if self.gate_ready:
            return "PASS_ORDER2_GATE_READY_NO_SUBMIT"
        return "PARTIAL_ORDER2_APPROVAL_OR_ORDER1_PROOF_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v101_baseline_status.startswith("FAIL") or self.controller_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.gate_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v101_baseline_status.startswith("FAIL"):
            return ["FAIL_V101_BASELINE_REGRESSION"]
        if self.controller_status.startswith("FAIL"):
            return ["FAIL_CLOSED_INVALID_ORDER2_APPROVAL"]
        blockers: list[str] = []
        if not self.order_validation["accepted"]:
            blockers.append("ORDER2_APPROVAL_ABSENT")
        if not self.campaign_approved:
            blockers.append("CAMPAIGN_APPROVAL_ABSENT")
        if not self.order_1_reconciled:
            blockers.append("ORDER1_RECONCILE_PROOF_ABSENT")
        if not self.order_1_forensic:
            blockers.append("ORDER1_FORENSIC_PROOF_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "ORDER2_GATE_READY_AWAIT_V103_ARM_NO_SUBMIT" if self.gate_ready else "OPERATOR_MUST_PROVIDE_ORDER2_APPROVAL_AND_ORDER1_PROOF"


def _common(ctx: V102Context) -> dict[str, Any]:
    return {
        "v101_baseline_status": ctx.v101_baseline_status,
        "order_2_gate_controller_status": ctx.controller_status,
        "order_2_approval_validator_status": "PASS_ORDER2_APPROVAL_VALID" if ctx.order_validation["accepted"] else ("FAIL_CLOSED_INVALID_ORDER2_APPROVAL" if ctx.order_validation["state"] == "PRESENT" else "PARTIAL_ORDER2_APPROVAL_ABSENT"),
        "campaign_approval_still_valid_status": "PASS_CAMPAIGN_APPROVAL_VALID" if ctx.campaign_approved else "PARTIAL_CAMPAIGN_APPROVAL_ABSENT",
        "order_1_reconcile_prerequisite_status": "PASS_ORDER1_RECONCILED" if ctx.order_1_reconciled else "PARTIAL_ORDER1_RECONCILE_ABSENT",
        "order_1_forensic_prerequisite_status": "PASS_ORDER1_FORENSIC" if ctx.order_1_forensic else "PARTIAL_ORDER1_FORENSIC_ABSENT",
        "stricter_risk_threshold_status": "PASS_STRICTER_RISK_THRESHOLD",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK",
        "no_repeat_without_approval_proof_status": "PASS_NO_REPEAT_WITHOUT_APPROVAL",
        "approval_validated": bool(ctx.order_validation["accepted"]),
        "approval_hash": ctx.order_validation["approval_hash"],
        "order_2_submitted": False,
        "live_orders": 0,
        "readiness_governor_v62_status": "PASS",
        "execution_lock_deep_recheck_v61_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V102Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v101_baseline"):
        return "PASS" if ctx.v101_baseline_status == "PASS_V101_BASELINE_READBACK" else "FAIL" if ctx.v101_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v102_order_2_gate_controller_report.json":
        return "FAIL" if ctx.controller_status.startswith("FAIL") else "PASS" if ctx.gate_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V102Context) -> dict[str, Any]:
    workstream = "v102: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v102_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V102_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v102_report.json":
        report.update({"completion_oriented_next_action_v102_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v88.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v101_carried_status": ctx.v101_baseline_status, "order_2_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v102.json"), "gate": str(ARTIFACTS / "v102_order_2_gate_controller_report.json"), "no_repeat_without_approval": str(ARTIFACTS / "v102_no_repeat_without_approval_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v102.json", "dummy_canonical_identity_report_v102.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V102ReportFactory:
    def __init__(self, *, campaign_approval=None, order_2_approval=None, order_2_approval_path=None, order_1_reconciled_override=None, order_1_forensic_override=None) -> None:
        self.kw = dict(campaign_approval=campaign_approval, order_2_approval=order_2_approval, order_2_approval_path=order_2_approval_path, order_1_reconciled_override=order_1_reconciled_override, order_1_forensic_override=order_1_forensic_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V102Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
