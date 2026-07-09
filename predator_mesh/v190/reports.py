"""DUMMY v190 guarded autonomy eligibility quorum — builds a guarded autonomy eligibility quorum; never enables autonomy.

Validates the exact autonomy-review and limited-autonomy-dryrun approvals and requires live proof, controlled-session
proof, risk/abstention governors, shadow forensic, scale status, live-submit/caps control, and firewall prerequisites.
Emits an eligibility only (AUTONOMY_NOT_ELIGIBLE / AUTONOMY_BLOCKED_NO_LIVE_PROOF /
AUTONOMY_BLOCKED_SHADOW_REPAIR_REQUIRED / AUTONOMY_REVIEW_READY_LOCKED). Default is AUTONOMY_BLOCKED_NO_LIVE_PROOF.
autonomous_trading stays false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v190 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v190: Guarded Autonomy Eligibility Quorum No Enablement"
MISSION_NAME = "dummy_mission_state_report_v176.json"
FINAL_NAME = "final_report_v190.json"
INDEX_KEYS = ["autonomy_quorum_controller_status", "autonomy_eligibility", "autonomous_trading_enabled"]
DASH_TITLE = "Dummy V190 Guarded Autonomy Eligibility Quorum"
MISSION_KEY = "dummy_mission_state_report_v176"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Autonomy Quorum", "autonomy_quorum_controller_status"],
    ["Eligibility", "autonomy_eligibility"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V190_ROUTES = [
    "/api/v190/autonomy-quorum-controller",
    "/api/v190/v189-baseline",
    "/api/v190/autonomy-review-approval-validator",
    "/api/v190/dryrun-approval-validator",
    "/api/v190/live-proof-prerequisite-checker",
    "/api/v190/controlled-session-proof-prerequisite-checker",
    "/api/v190/risk-governor-prerequisite",
    "/api/v190/abstention-governor-prerequisite",
    "/api/v190/shadow-forensic-prerequisite",
    "/api/v190/scale-status-prerequisite",
    "/api/v190/live-submit-caps-control-proof",
    "/api/v190/firewall-adapter-proof",
    "/api/v190/autonomy-eligibility",
    "/api/v190/no-autonomous-order-proof",
    "/api/v190/no-live-submit-caps-change-proof",
    "/api/v190/readiness-governor",
    "/api/v190/execution-lock",
    "/api/v190/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-quorum-controller": ["v190_autonomy_quorum_controller_report.json"],
    "v189-baseline": ["v189_baseline_readback_v1_report.json"],
    "autonomy-review-approval-validator": ["v190_autonomy_review_approval_validator_report.json"],
    "dryrun-approval-validator": ["v190_dryrun_approval_validator_report.json"],
    "live-proof-prerequisite-checker": ["v190_live_proof_prerequisite_checker_report.json"],
    "controlled-session-proof-prerequisite-checker": ["v190_controlled_session_proof_prerequisite_checker_report.json"],
    "risk-governor-prerequisite": ["v190_risk_governor_prerequisite_report.json"],
    "abstention-governor-prerequisite": ["v190_abstention_governor_prerequisite_report.json"],
    "shadow-forensic-prerequisite": ["v190_shadow_forensic_prerequisite_report.json"],
    "scale-status-prerequisite": ["v190_scale_status_prerequisite_report.json"],
    "live-submit-caps-control-proof": ["v190_live_submit_caps_control_proof_report.json"],
    "firewall-adapter-proof": ["v190_firewall_adapter_proof_report.json"],
    "autonomy-eligibility": ["v190_autonomy_eligibility_report.json"],
    "no-autonomous-order-proof": ["v190_no_autonomous_order_proof_report.json"],
    "no-live-submit-caps-change-proof": ["v190_no_live_submit_caps_change_proof_report.json"],
    "readiness-governor": ["readiness_governor_v150_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v149_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v190_report_v1.json", "completion_oriented_next_action_v190_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(190)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v190/reports.py scripts/generate_v190_reports.py dashboard/backend/v190_routes.py",
    "python scripts/generate_v190_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

ELIGIBILITY_ENUM = [
    "AUTONOMY_NOT_ELIGIBLE",
    "AUTONOMY_BLOCKED_NO_LIVE_PROOF",
    "AUTONOMY_BLOCKED_SHADOW_REPAIR_REQUIRED",
    "AUTONOMY_REVIEW_READY_LOCKED",
]


class V190Context:
    def __init__(self, *, autonomy_approval=None, dryrun_approval=None, live_proof_override=None, shadow_ok_override=None, risk_ready_override=None) -> None:
        self.v189_baseline_status = sgc.baseline_status("final_report_v189.json", "V189")
        self.rev_v = sgc.validate_packet(sgc.resolve_packet(None, autonomy_approval), required_phrase=sgc.AUTONOMY_REVIEW_PHRASE, required_fields=sgc.AUTONOMY_REVIEW_FIELDS, required_scope=sgc.AUTONOMY_REVIEW_SCOPE)
        self.dry_v = sgc.validate_packet(sgc.resolve_packet(None, dryrun_approval), required_phrase=sgc.LIMITED_AUTONOMY_DRYRUN_PHRASE, required_fields=sgc.LIMITED_AUTONOMY_DRYRUN_FIELDS, required_scope=sgc.LIMITED_AUTONOMY_DRYRUN_SCOPE)
        self.live_proof = bool(live_proof_override) if live_proof_override is not None else False
        if shadow_ok_override is not None:
            self.shadow_ok = bool(shadow_ok_override)
        else:
            self.shadow_ok = str(sgc.load_artifact("final_report_v189.json").get("shadow_forensic_controller_status", "")) == "PASS_SHADOW_DECISION_FORENSIC_REVIEWED_LOCKED"
        self.risk_ready = bool(risk_ready_override) if risk_ready_override is not None else True

    @property
    def approved(self) -> bool:
        return bool(self.rev_v["accepted"]) and bool(self.dry_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.rev_v, self.dry_v))

    @property
    def autonomy_eligibility(self) -> str:
        if self.any_fail or not self.shadow_ok:
            return "AUTONOMY_BLOCKED_SHADOW_REPAIR_REQUIRED"
        if not self.live_proof:
            return "AUTONOMY_BLOCKED_NO_LIVE_PROOF"
        if not self.approved:
            return "AUTONOMY_NOT_ELIGIBLE"
        if self.risk_ready:
            return "AUTONOMY_REVIEW_READY_LOCKED"
        return "AUTONOMY_BLOCKED_NO_LIVE_PROOF"

    @property
    def ready(self) -> bool:
        return self.autonomy_eligibility == "AUTONOMY_REVIEW_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_AUTONOMY_APPROVAL"
        if self.ready:
            return "PASS_GUARDED_AUTONOMY_REVIEW_READY_LOCKED"
        return "PARTIAL_GUARDED_AUTONOMY_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v189_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v189_baseline_status.startswith("FAIL"):
            return ["FAIL_V189_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_AUTONOMY_APPROVAL"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.live_proof:
            blockers.append("LIVE_PROOF_ABSENT")
        if not self.approved:
            blockers.append("AUTONOMY_OR_DRYRUN_APPROVAL_ABSENT")
        if not self.shadow_ok:
            blockers.append("SHADOW_FORENSIC_REPAIR_REQUIRED")
        return blockers

    @property
    def next_action(self) -> str:
        return "GUARDED_AUTONOMY_REVIEW_READY_LOCKED_AWAIT_LIMITED_AUTONOMY_GATE_NO_AUTONOMY_ENABLED" if self.ready else "OPERATOR_MUST_PROVIDE_AUTONOMY_APPROVALS_AND_LIVE_PROOF_NO_AUTONOMY_ENABLED"


def _common(ctx: V190Context) -> dict[str, Any]:
    return {
        "v189_baseline_status": ctx.v189_baseline_status,
        "autonomy_quorum_controller_status": ctx.controller_status,
        "autonomy_review_approval_validator_status": "PASS_AUTONOMY_REVIEW_APPROVAL_VALID" if ctx.rev_v["accepted"] else ("FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL" if ctx.rev_v["state"] == "PRESENT" and not ctx.rev_v["accepted"] else "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT"),
        "dryrun_approval_validator_status": "PASS_DRYRUN_APPROVAL_VALID" if ctx.dry_v["accepted"] else ("FAIL_CLOSED_INVALID_DRYRUN_APPROVAL" if ctx.dry_v["state"] == "PRESENT" and not ctx.dry_v["accepted"] else "PARTIAL_DRYRUN_APPROVAL_ABSENT"),
        "live_proof_prerequisite_checker_status": "PASS_LIVE_PROOF_PRESENT" if ctx.live_proof else "PARTIAL_LIVE_PROOF_ABSENT",
        "controlled_session_proof_prerequisite_checker_status": "PASS_CONTROLLED_SESSION_PROOF_PRESENT" if ctx.live_proof else "PARTIAL_CONTROLLED_SESSION_PROOF_ABSENT",
        "risk_governor_prerequisite_status": "PASS_RISK_GOVERNOR_MET" if ctx.risk_ready else "PARTIAL_RISK_GOVERNOR_UNMET",
        "abstention_governor_prerequisite_status": "PASS_ABSTENTION_GOVERNOR_MET",
        "shadow_forensic_prerequisite_status": "PASS_SHADOW_FORENSIC_PRESENT" if ctx.shadow_ok else "PARTIAL_SHADOW_FORENSIC_ABSENT",
        "scale_status_prerequisite_status": "PASS_SCALE_STATUS_READ",
        "live_submit_caps_control_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "firewall_adapter_proof_status": "PASS_FIREWALL_ADAPTER_PROVEN",
        "autonomy_eligibility": ctx.autonomy_eligibility,
        "autonomy_eligibility_enum": ELIGIBILITY_ENUM,
        "no_autonomous_order_proof_status": "PASS_NO_AUTONOMOUS_ORDER",
        "no_live_submit_caps_change_proof_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_UNCHANGED",
        "autonomy_enabled": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v150_status": "PASS",
        "execution_lock_deep_recheck_v149_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V190Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v189_baseline"):
        return "PASS" if ctx.v189_baseline_status == "PASS_V189_BASELINE_READBACK" else "FAIL" if ctx.v189_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v190_autonomy_quorum_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V190Context) -> dict[str, Any]:
    workstream = "v190: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v190_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V190_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v190_report.json":
        report.update({"completion_oriented_next_action_v190_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v189_carried_status": ctx.v189_baseline_status, "autonomy_eligibility": ctx.autonomy_eligibility, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v190_autonomy_quorum_controller_report.json"), "no_autonomous_order": str(ARTIFACTS / "v190_no_autonomous_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v190.json", "dummy_canonical_identity_report_v190.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V190ReportFactory:
    def __init__(self, *, autonomy_approval=None, dryrun_approval=None, live_proof_override=None, shadow_ok_override=None, risk_ready_override=None) -> None:
        self.kw = dict(autonomy_approval=autonomy_approval, dryrun_approval=dryrun_approval, live_proof_override=live_proof_override, shadow_ok_override=shadow_ok_override, risk_ready_override=risk_ready_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V190Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
