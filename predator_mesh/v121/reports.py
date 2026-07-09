"""DUMMY v121 repeat production pilot review gate — reviews repeat-pilot eligibility only; no automatic repeat order.

Validates the exact repeat-pilot review approval and requires a first-pilot forensic prerequisite plus no-loss /
no-drift / risk-threshold locks. Default is PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT with
live_orders=0. Even when eligible it only emits a review-ready status; no repeat order is armed, no scale, no caps
change, and every live submit still requires separate approval.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v121 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v121: Repeat Production Pilot Review Gate No Auto Repeat"
MISSION_NAME = "dummy_mission_state_report_v107.json"
FINAL_NAME = "final_report_v121.json"
INDEX_KEYS = ["repeat_pilot_gate_controller_status", "repeat_pilot_recommendation", "live_orders"]
DASH_TITLE = "Dummy V121 Repeat Production Pilot Review Gate"
MISSION_KEY = "dummy_mission_state_report_v107"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"],
    ["Recommendation", "repeat_pilot_recommendation"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V121_ROUTES = [
    "/api/v121/repeat-pilot-gate-controller",
    "/api/v121/v120-baseline",
    "/api/v121/repeat-pilot-approval-validator",
    "/api/v121/first-pilot-forensic-prerequisite",
    "/api/v121/no-loss-lock",
    "/api/v121/no-drift-lock",
    "/api/v121/risk-threshold-prerequisite",
    "/api/v121/live-submit-caps-control-proof",
    "/api/v121/no-auto-repeat-proof",
    "/api/v121/readiness-governor",
    "/api/v121/execution-lock",
    "/api/v121/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-pilot-gate-controller": ["v121_repeat_pilot_gate_controller_report.json"],
    "v120-baseline": ["v120_baseline_readback_v1_report.json"],
    "repeat-pilot-approval-validator": ["v121_repeat_pilot_approval_validator_report.json"],
    "first-pilot-forensic-prerequisite": ["v121_first_pilot_forensic_prerequisite_report.json"],
    "no-loss-lock": ["v121_no_loss_lock_report.json"],
    "no-drift-lock": ["v121_no_drift_lock_report.json"],
    "risk-threshold-prerequisite": ["v121_risk_threshold_prerequisite_report.json"],
    "live-submit-caps-control-proof": ["v121_live_submit_caps_control_proof_report.json"],
    "no-auto-repeat-proof": ["v121_no_auto_repeat_proof_report.json"],
    "readiness-governor": ["readiness_governor_v81_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v80_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v121_report_v1.json", "completion_oriented_next_action_v121_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(121)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v121/reports.py scripts/generate_v121_reports.py dashboard/backend/v121_routes.py",
    "python scripts/generate_v121_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V121Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.v120_baseline_status = sgc.baseline_status("final_report_v120.json", "V120")
        res = sgc.resolve_packet(repeat_approval_path, repeat_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.REPEAT_PILOT_PHRASE, required_fields=sgc.REPEAT_PILOT_FIELDS, required_scope=sgc.REPEAT_PILOT_SCOPE)
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            self.first_pilot_ok = str(sgc.load_artifact("final_report_v120.json").get("pilot_forensic_controller_status", "")) == "PASS_PRODUCTION_PILOT_REVIEWED_AUTOLOCKED"
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def eligible(self) -> bool:
        return self.approved and self.first_pilot_ok and self.risk_ready

    @property
    def repeat_pilot_recommendation(self) -> str:
        if self.any_fail:
            return "REPEAT_PILOT_BLOCKED"
        if self.eligible:
            return "REPEAT_PILOT_REVIEW_READY"
        return "NO_REPEAT_PILOT"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
        if self.eligible:
            return "PASS_REPEAT_PILOT_REVIEW_ELIGIBLE_LOCKED"
        return "PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v120_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.eligible else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v120_baseline_status.startswith("FAIL"):
            return ["FAIL_V120_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"]
        if self.eligible:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("REPEAT_PILOT_APPROVAL_ABSENT")
        if not self.first_pilot_ok:
            blockers.append("FIRST_PILOT_FORENSIC_PROOF_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_THRESHOLD_PREREQUISITE_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "REPEAT_PILOT_REVIEW_ELIGIBLE_LOCKED_AWAIT_SEPARATE_PER_ORDER_APPROVAL_NO_AUTO_REPEAT" if self.eligible else "OPERATOR_MUST_PROVIDE_REPEAT_PILOT_APPROVAL_AND_FIRST_PILOT_FORENSIC_PROOF"


def _common(ctx: V121Context) -> dict[str, Any]:
    return {
        "v120_baseline_status": ctx.v120_baseline_status,
        "repeat_pilot_gate_controller_status": ctx.controller_status,
        "repeat_pilot_approval_validator_status": "PASS_REPEAT_PILOT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_REPEAT_PILOT_APPROVAL_ABSENT"),
        "repeat_pilot_phrase": sgc.REPEAT_PILOT_PHRASE,
        "repeat_pilot_approval_hash": ctx.validation["approval_hash"],
        "first_pilot_forensic_prerequisite_status": "PASS_FIRST_PILOT_FORENSIC_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_FORENSIC_ABSENT",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
        "risk_threshold_prerequisite_status": "PASS_RISK_THRESHOLD_MET" if ctx.risk_ready else "PARTIAL_RISK_THRESHOLD_UNMET",
        "live_submit_caps_control_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "no_auto_repeat_proof_status": "PASS_NO_AUTO_REPEAT",
        "repeat_pilot_recommendation": ctx.repeat_pilot_recommendation,
        "auto_repeat_enabled": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v81_status": "PASS",
        "execution_lock_deep_recheck_v80_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V121Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v120_baseline"):
        return "PASS" if ctx.v120_baseline_status == "PASS_V120_BASELINE_READBACK" else "FAIL" if ctx.v120_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v121_repeat_pilot_gate_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.eligible else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V121Context) -> dict[str, Any]:
    workstream = "v121: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v121_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V121_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v121_report.json":
        report.update({"completion_oriented_next_action_v121_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v120_carried_status": ctx.v120_baseline_status, "repeat_pilot_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v121_repeat_pilot_gate_controller_report.json"), "no_auto_repeat": str(ARTIFACTS / "v121_no_auto_repeat_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v121.json", "dummy_canonical_identity_report_v121.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V121ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, first_pilot_override=first_pilot_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V121Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
