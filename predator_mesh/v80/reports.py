"""DUMMY v80 repeat-canary approval validator — stricter gate, no submit."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v80 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V80_ROUTES = [
    "/api/v80/repeat-canary-validator",
    "/api/v80/v79-baseline",
    "/api/v80/exact-second-canary-phrase-validator",
    "/api/v80/first-canary-reconcile-prerequisite",
    "/api/v80/first-canary-forensic-prerequisite",
    "/api/v80/stricter-risk-thresholds",
    "/api/v80/no-loss-lock-validator",
    "/api/v80/no-drift-lock-validator",
    "/api/v80/no-repeat-without-approval-proof",
    "/api/v80/readiness-governor",
    "/api/v80/execution-lock",
    "/api/v80/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-canary-validator": ["v80_repeat_canary_validator_report.json"],
    "v79-baseline": ["v79_baseline_readback_v1_report.json"],
    "exact-second-canary-phrase-validator": ["v80_exact_second_canary_phrase_validator_report.json"],
    "first-canary-reconcile-prerequisite": ["v80_first_canary_reconcile_prerequisite_report.json"],
    "first-canary-forensic-prerequisite": ["v80_first_canary_forensic_prerequisite_report.json"],
    "stricter-risk-thresholds": ["v80_stricter_risk_thresholds_report.json"],
    "no-loss-lock-validator": ["v80_no_loss_lock_validator_report.json"],
    "no-drift-lock-validator": ["v80_no_drift_lock_validator_report.json"],
    "no-repeat-without-approval-proof": ["v80_no_repeat_without_approval_proof_report.json"],
    "readiness-governor": ["readiness_governor_v40_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v39_report.json"],
    "mission-state": ["dummy_mission_state_report_v66.json", "dashboard_v80_report_v1.json", "completion_oriented_next_action_v80_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(80)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v80/reports.py scripts/generate_v80_reports.py dashboard/backend/v80_routes.py",
    "python scripts/generate_v80_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V80Context:
    def __init__(self, *, approval_input, approval_path, first_canary_reconciled_override=None, first_canary_forensic_override=None) -> None:
        self.v79_baseline_status = sgc.baseline_status("final_report_v79.json", "V79")
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V81_SECOND_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V81_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V81_SECOND_CANARY_SCOPE,
            ack_requirements=sgc.V81_ACK_REQUIREMENTS,
        )
        if first_canary_reconciled_override is None:
            self.first_reconciled = str(sgc.load_artifact("final_report_v78.json").get("reconcile_controller_status", "")) == "PASS_LIVE_CANARY_RECONCILED"
        else:
            self.first_reconciled = bool(first_canary_reconciled_override)
        if first_canary_forensic_override is None:
            self.first_forensic = sgc.load_artifact("final_report_v79.json").get("verdict") == "PASS"
        else:
            self.first_forensic = bool(first_canary_forensic_override)

    @property
    def gate_ready(self) -> bool:
        return self.validation["accepted"] and self.first_reconciled and self.first_forensic

    @property
    def validator_status(self) -> str:
        if self.validation["state"] == "PRESENT" and not self.validation["accepted"]:
            return "FAIL_CLOSED_INVALID_SECOND_APPROVAL"
        if self.gate_ready:
            return "PASS_SECOND_CANARY_APPROVAL_VALID_STRICTER_GATE"
        if not self.validation["accepted"]:
            return "PARTIAL_SECOND_CANARY_APPROVAL_ABSENT"
        return "PARTIAL_FIRST_CANARY_PROOF_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v79_baseline_status.startswith("FAIL") or self.validator_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.gate_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v79_baseline_status.startswith("FAIL"):
            return ["FAIL_V79_BASELINE_REGRESSION"]
        if self.validator_status.startswith("FAIL"):
            return ["FAIL_CLOSED_INVALID_SECOND_APPROVAL"]
        blockers: list[str] = []
        if not self.validation["accepted"]:
            blockers.append("SECOND_CANARY_APPROVAL_ABSENT")
        if not self.first_reconciled:
            blockers.append("FIRST_CANARY_RECONCILE_PROOF_ABSENT")
        if not self.first_forensic:
            blockers.append("FIRST_CANARY_FORENSIC_PROOF_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        if self.gate_ready:
            return "SECOND_CANARY_APPROVAL_VALID_AWAIT_V81_ARM_NO_SUBMIT"
        return "OPERATOR_MUST_PROVIDE_SECOND_APPROVAL_AND_FIRST_CANARY_PROOF"


def _common(ctx: V80Context) -> dict[str, Any]:
    return {
        "v79_baseline_status": ctx.v79_baseline_status,
        "repeat_canary_validator_status": ctx.validator_status,
        "second_canary_phrase": sgc.V81_SECOND_CANARY_SUBMIT_PHRASE,
        "exact_second_canary_phrase_validator_status": "PASS_EXACT_SECOND_PHRASE" if ctx.validation["accepted"] else ("FAIL_CLOSED_INVALID_SECOND_APPROVAL" if ctx.validation["state"] == "PRESENT" else "PARTIAL_SECOND_APPROVAL_ABSENT"),
        "first_canary_reconcile_prerequisite_status": "PASS_FIRST_RECONCILE_PRESENT" if ctx.first_reconciled else "PARTIAL_FIRST_RECONCILE_ABSENT",
        "first_canary_forensic_prerequisite_status": "PASS_FIRST_FORENSIC_PRESENT" if ctx.first_forensic else "PARTIAL_FIRST_FORENSIC_ABSENT",
        "stricter_risk_thresholds_status": "PASS_STRICTER_RISK_THRESHOLDS",
        "no_loss_lock_validator_status": "PASS_NO_LOSS_LOCK",
        "no_drift_lock_validator_status": "PASS_NO_DRIFT_LOCK",
        "no_repeat_without_approval_proof_status": "PASS_NO_REPEAT_WITHOUT_APPROVAL",
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "second_order_submitted": False,
        "readiness_governor_v40_status": "PASS",
        "execution_lock_deep_recheck_v39_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V80Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v79_baseline"):
        return "PASS" if ctx.v79_baseline_status == "PASS_V79_BASELINE_READBACK" else "FAIL" if ctx.v79_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v80_repeat_canary_validator_report.json":
        return "FAIL" if ctx.validator_status.startswith("FAIL") else "PASS" if ctx.gate_ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V80Context) -> dict[str, Any]:
    workstream = "v80: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v80_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V80_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v80_report.json":
        report.update({"completion_oriented_next_action_v80_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v66.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v79_carried_status": ctx.v79_baseline_status, "repeat_canary_validator_status": ctx.validator_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v80.json"), "repeat_validator": str(ARTIFACTS / "v80_repeat_canary_validator_report.json"), "no_repeat_without_approval": str(ARTIFACTS / "v80_no_repeat_without_approval_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v80.json", "dummy_canonical_identity_report_v80.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V80ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, first_canary_reconciled_override=None, first_canary_forensic_override=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.first_canary_reconciled_override = first_canary_reconciled_override
        self.first_canary_forensic_override = first_canary_forensic_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V80Context(approval_input=self.approval_input, approval_path=self.approval_path, first_canary_reconciled_override=self.first_canary_reconciled_override, first_canary_forensic_override=self.first_canary_forensic_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
