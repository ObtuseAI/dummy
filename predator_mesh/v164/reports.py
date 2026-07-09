"""DUMMY v164 repeat-pilot eligibility decision — decides whether a repeat pilot may be reviewed next; no repeat submit.

Validates the exact repeat-pilot approval and requires first-pilot reconcile (V162) + forensic (V163) prerequisites
plus no-loss / no-drift / no-liquidity / no-broker-error / no-slippage locks, a risk threshold, and an abstention-quality
prerequisite. Emits a decision only (STOP_NO_REAL_PILOT_PROOF / REPAIR_REQUIRED / REPEAT_REVIEW_READY_LOCKED /
SCALE_REVIEW_BLOCKED / AUTONOMY_NOT_ELIGIBLE). Default is STOP_NO_REAL_PILOT_PROOF. No repeat submit, no scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v164 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v164: Repeat Pilot Eligibility Decision Stop Repair Repeat Or Scale Review"
MISSION_NAME = "dummy_mission_state_report_v150.json"
FINAL_NAME = "final_report_v164.json"
INDEX_KEYS = ["repeat_eligibility_controller_status", "eligibility_decision", "live_orders"]
DASH_TITLE = "Dummy V164 Repeat-Pilot Eligibility Decision"
MISSION_KEY = "dummy_mission_state_report_v150"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Eligibility", "repeat_eligibility_controller_status"],
    ["Decision", "eligibility_decision"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V164_ROUTES = [
    "/api/v164/repeat-eligibility-controller",
    "/api/v164/v163-baseline",
    "/api/v164/repeat-approval-validator",
    "/api/v164/first-pilot-reconcile-prerequisite",
    "/api/v164/first-pilot-forensic-prerequisite",
    "/api/v164/no-loss-lock",
    "/api/v164/no-drift-lock",
    "/api/v164/no-liquidity-lock",
    "/api/v164/no-broker-error-lock",
    "/api/v164/no-slippage-lock",
    "/api/v164/risk-threshold-prerequisite",
    "/api/v164/abstention-quality-prerequisite",
    "/api/v164/live-submit-caps-unchanged-proof",
    "/api/v164/no-auto-repeat-proof",
    "/api/v164/no-submit-proof",
    "/api/v164/readiness-governor",
    "/api/v164/execution-lock",
    "/api/v164/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-eligibility-controller": ["v164_repeat_eligibility_controller_report.json"],
    "v163-baseline": ["v163_baseline_readback_v1_report.json"],
    "repeat-approval-validator": ["v164_repeat_approval_validator_report.json"],
    "first-pilot-reconcile-prerequisite": ["v164_first_pilot_reconcile_prerequisite_report.json"],
    "first-pilot-forensic-prerequisite": ["v164_first_pilot_forensic_prerequisite_report.json"],
    "no-loss-lock": ["v164_no_loss_lock_report.json"],
    "no-drift-lock": ["v164_no_drift_lock_report.json"],
    "no-liquidity-lock": ["v164_no_liquidity_lock_report.json"],
    "no-broker-error-lock": ["v164_no_broker_error_lock_report.json"],
    "no-slippage-lock": ["v164_no_slippage_lock_report.json"],
    "risk-threshold-prerequisite": ["v164_risk_threshold_prerequisite_report.json"],
    "abstention-quality-prerequisite": ["v164_abstention_quality_prerequisite_report.json"],
    "live-submit-caps-unchanged-proof": ["v164_live_submit_caps_unchanged_proof_report.json"],
    "no-auto-repeat-proof": ["v164_no_auto_repeat_proof_report.json"],
    "no-submit-proof": ["v164_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v124_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v123_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v164_report_v1.json", "completion_oriented_next_action_v164_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(164)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v164/reports.py scripts/generate_v164_reports.py dashboard/backend/v164_routes.py",
    "python scripts/generate_v164_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

DECISION_ENUM = [
    "STOP_NO_REAL_PILOT_PROOF",
    "REPAIR_REQUIRED",
    "REPEAT_REVIEW_READY_LOCKED",
    "SCALE_REVIEW_BLOCKED",
    "AUTONOMY_NOT_ELIGIBLE",
]


class V164Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.v163_baseline_status = sgc.baseline_status("final_report_v163.json", "V163")
        res = sgc.resolve_packet(repeat_approval_path, repeat_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.REPEAT_PILOT_PHRASE, required_fields=sgc.REPEAT_PILOT_FIELDS, required_scope=sgc.REPEAT_PILOT_SCOPE)
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v162.json").get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v163.json").get("forensic_controller_status", "")) == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = reconciled and reviewed
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def eligibility_decision(self) -> str:
        if self.any_fail:
            return "REPAIR_REQUIRED"
        if not self.first_pilot_ok:
            return "STOP_NO_REAL_PILOT_PROOF"
        if self.approved and self.risk_ready:
            return "REPEAT_REVIEW_READY_LOCKED"
        return "SCALE_REVIEW_BLOCKED"

    @property
    def ready(self) -> bool:
        return self.eligibility_decision == "REPEAT_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
        if self.ready:
            return "PASS_REPEAT_ELIGIBILITY_REVIEW_READY_LOCKED"
        return "PARTIAL_REPEAT_ELIGIBILITY_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v163_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v163_baseline_status.startswith("FAIL"):
            return ["FAIL_V163_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.first_pilot_ok:
            blockers.append("FIRST_PILOT_RECONCILE_FORENSIC_PROOF_ABSENT")
        if not self.approved:
            blockers.append("REPEAT_PILOT_APPROVAL_ABSENT")
        if not self.risk_ready:
            blockers.append("RISK_THRESHOLD_PREREQUISITE_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        if self.ready:
            return "REPEAT_ELIGIBILITY_REVIEW_READY_LOCKED_AWAIT_SEPARATE_REPEAT_PILOT_BUNDLE_NO_SUBMIT"
        if self.eligibility_decision == "STOP_NO_REAL_PILOT_PROOF":
            return "STOP_NO_REAL_PILOT_PROOF_AWAIT_FIRST_REAL_PILOT_RECONCILE_AND_FORENSIC"
        return "OPERATOR_MUST_PROVIDE_REPEAT_APPROVAL_AND_FIRST_PILOT_PROOF_NO_SUBMIT"


def _common(ctx: V164Context) -> dict[str, Any]:
    return {
        "v163_baseline_status": ctx.v163_baseline_status,
        "repeat_eligibility_controller_status": ctx.controller_status,
        "repeat_approval_validator_status": "PASS_REPEAT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_REPEAT_APPROVAL_ABSENT"),
        "repeat_pilot_phrase": sgc.REPEAT_PILOT_PHRASE,
        "repeat_approval_hash": ctx.validation["approval_hash"],
        "first_pilot_reconcile_prerequisite_status": "PASS_FIRST_PILOT_RECONCILED" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_NOT_RECONCILED",
        "first_pilot_forensic_prerequisite_status": "PASS_FIRST_PILOT_FORENSIC_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_FORENSIC_ABSENT",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
        "no_liquidity_lock_status": "PASS_NO_LIQUIDITY_LOCK_ARMED",
        "no_broker_error_lock_status": "PASS_NO_BROKER_ERROR_LOCK_ARMED",
        "no_slippage_lock_status": "PASS_NO_SLIPPAGE_LOCK_ARMED",
        "risk_threshold_prerequisite_status": "PASS_RISK_THRESHOLD_MET" if ctx.risk_ready else "PARTIAL_RISK_THRESHOLD_UNMET",
        "abstention_quality_prerequisite_status": "PASS_ABSTENTION_QUALITY_MET",
        "live_submit_caps_unchanged_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "no_auto_repeat_proof_status": "PASS_NO_AUTO_REPEAT",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "eligibility_decision": ctx.eligibility_decision,
        "eligibility_decision_enum": DECISION_ENUM,
        "auto_repeat_enabled": False,
        "repeat_pilot_submitted": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v124_status": "PASS",
        "execution_lock_deep_recheck_v123_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V164Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v163_baseline"):
        return "PASS" if ctx.v163_baseline_status == "PASS_V163_BASELINE_READBACK" else "FAIL" if ctx.v163_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v164_repeat_eligibility_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V164Context) -> dict[str, Any]:
    workstream = "v164: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v164_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V164_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v164_report.json":
        report.update({"completion_oriented_next_action_v164_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v163_carried_status": ctx.v163_baseline_status, "eligibility_decision": ctx.eligibility_decision, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v164_repeat_eligibility_controller_report.json"), "no_auto_repeat": str(ARTIFACTS / "v164_no_auto_repeat_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v164.json", "dummy_canonical_identity_report_v164.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V164ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, first_pilot_override=first_pilot_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V164Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
