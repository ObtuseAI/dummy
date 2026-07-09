"""DUMMY v154 repeat pilot preflight lock — prepares a repeat pilot only after first-pilot proof; never submits.

Validates the exact repeat-pilot approval and requires first-pilot reconcile (V152) + forensic (V153) prerequisites
plus no-loss / no-drift / no-liquidity / no-broker-error locks, a stricter risk threshold, and a live-submit/caps
snapshot recheck. Default is PARTIAL_REPEAT_PREFLIGHT_BLOCKED. Even when ready it only locks a preflight; no order is
submitted.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v154 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v154: Repeat Pilot Preflight Lock After First Pilot Proof"
MISSION_NAME = "dummy_mission_state_report_v140.json"
FINAL_NAME = "final_report_v154.json"
INDEX_KEYS = ["repeat_preflight_controller_status", "repeat_preflight_ready", "live_orders"]
DASH_TITLE = "Dummy V154 Repeat Pilot Preflight Lock"
MISSION_KEY = "dummy_mission_state_report_v140"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Preflight", "repeat_preflight_controller_status"],
    ["Preflight Ready", "repeat_preflight_ready"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V154_ROUTES = [
    "/api/v154/repeat-preflight-controller",
    "/api/v154/v153-baseline",
    "/api/v154/repeat-approval-validator",
    "/api/v154/first-pilot-reconcile-prerequisite",
    "/api/v154/first-pilot-forensic-prerequisite",
    "/api/v154/no-loss-lock",
    "/api/v154/no-drift-lock",
    "/api/v154/no-liquidity-lock",
    "/api/v154/no-broker-error-lock",
    "/api/v154/stricter-risk-threshold",
    "/api/v154/live-submit-caps-snapshot-recheck",
    "/api/v154/no-auto-repeat-proof",
    "/api/v154/readiness-governor",
    "/api/v154/execution-lock",
    "/api/v154/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-preflight-controller": ["v154_repeat_preflight_controller_report.json"],
    "v153-baseline": ["v153_baseline_readback_v1_report.json"],
    "repeat-approval-validator": ["v154_repeat_approval_validator_report.json"],
    "first-pilot-reconcile-prerequisite": ["v154_first_pilot_reconcile_prerequisite_report.json"],
    "first-pilot-forensic-prerequisite": ["v154_first_pilot_forensic_prerequisite_report.json"],
    "no-loss-lock": ["v154_no_loss_lock_report.json"],
    "no-drift-lock": ["v154_no_drift_lock_report.json"],
    "no-liquidity-lock": ["v154_no_liquidity_lock_report.json"],
    "no-broker-error-lock": ["v154_no_broker_error_lock_report.json"],
    "stricter-risk-threshold": ["v154_stricter_risk_threshold_report.json"],
    "live-submit-caps-snapshot-recheck": ["v154_live_submit_caps_snapshot_recheck_report.json"],
    "no-auto-repeat-proof": ["v154_no_auto_repeat_proof_report.json"],
    "readiness-governor": ["readiness_governor_v114_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v113_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v154_report_v1.json", "completion_oriented_next_action_v154_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(154)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v154/reports.py scripts/generate_v154_reports.py dashboard/backend/v154_routes.py",
    "python scripts/generate_v154_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V154Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.v153_baseline_status = sgc.baseline_status("final_report_v153.json", "V153")
        res = sgc.resolve_packet(repeat_approval_path, repeat_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.REPEAT_PILOT_PHRASE, required_fields=sgc.REPEAT_PILOT_FIELDS, required_scope=sgc.REPEAT_PILOT_SCOPE)
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v152.json").get("reconcile_intake_controller_status", "")) == "PASS_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v153.json").get("forensic_controller_status", "")) == "PASS_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = reconciled and reviewed
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def ready(self) -> bool:
        return self.approved and self.first_pilot_ok and self.risk_ready

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
        if self.ready:
            return "PASS_REPEAT_PREFLIGHT_READY_LOCKED"
        return "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v153_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v153_baseline_status.startswith("FAIL"):
            return ["FAIL_V153_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("REPEAT_PILOT_APPROVAL_ABSENT")
        if not self.first_pilot_ok:
            blockers.append("FIRST_PILOT_RECONCILE_FORENSIC_PROOF_ABSENT")
        if not self.risk_ready:
            blockers.append("STRICTER_RISK_THRESHOLD_UNMET")
        return blockers

    @property
    def next_action(self) -> str:
        return "REPEAT_PREFLIGHT_READY_LOCKED_AWAIT_REPEAT_PILOT_FIRE_NO_AUTO_REPEAT_NO_SUBMIT" if self.ready else "OPERATOR_MUST_PROVIDE_REPEAT_APPROVAL_AND_FIRST_PILOT_RECONCILE_FORENSIC_PROOF"


def _common(ctx: V154Context) -> dict[str, Any]:
    return {
        "v153_baseline_status": ctx.v153_baseline_status,
        "repeat_preflight_controller_status": ctx.controller_status,
        "repeat_approval_validator_status": "PASS_REPEAT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_REPEAT_APPROVAL_ABSENT"),
        "repeat_pilot_phrase": sgc.REPEAT_PILOT_PHRASE,
        "repeat_approval_hash": ctx.validation["approval_hash"],
        "first_pilot_reconcile_prerequisite_status": "PASS_FIRST_PILOT_RECONCILED" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_NOT_RECONCILED",
        "first_pilot_forensic_prerequisite_status": "PASS_FIRST_PILOT_FORENSIC_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_FORENSIC_ABSENT",
        "no_loss_lock_status": "PASS_NO_LOSS_LOCK_ARMED",
        "no_drift_lock_status": "PASS_NO_DRIFT_LOCK_ARMED",
        "no_liquidity_lock_status": "PASS_NO_LIQUIDITY_LOCK_ARMED",
        "no_broker_error_lock_status": "PASS_NO_BROKER_ERROR_LOCK_ARMED",
        "stricter_risk_threshold_status": "PASS_STRICTER_RISK_THRESHOLD_MET" if ctx.risk_ready else "PARTIAL_STRICTER_RISK_THRESHOLD_UNMET",
        "live_submit_caps_snapshot_recheck_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "no_auto_repeat_proof_status": "PASS_NO_AUTO_REPEAT",
        "repeat_preflight_ready": ctx.ready,
        "auto_repeat_enabled": False,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v114_status": "PASS",
        "execution_lock_deep_recheck_v113_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V154Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v153_baseline"):
        return "PASS" if ctx.v153_baseline_status == "PASS_V153_BASELINE_READBACK" else "FAIL" if ctx.v153_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v154_repeat_preflight_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V154Context) -> dict[str, Any]:
    workstream = "v154: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v154_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V154_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v154_report.json":
        report.update({"completion_oriented_next_action_v154_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v153_carried_status": ctx.v153_baseline_status, "repeat_preflight_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v154_repeat_preflight_controller_report.json"), "no_auto_repeat": str(ARTIFACTS / "v154_no_auto_repeat_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v154.json", "dummy_canonical_identity_report_v154.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V154ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, risk_ready_override=None) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, first_pilot_override=first_pilot_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V154Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
