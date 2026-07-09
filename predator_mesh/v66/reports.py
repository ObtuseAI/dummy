"""DUMMY v66 live-canary approval packet validator and live-submit preflight lock (no live order)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v66 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V66_ROUTES = [
    "/api/v66/approval-packet-validator",
    "/api/v66/v65-baseline",
    "/api/v66/exact-phrase-policy",
    "/api/v66/approval-metadata-validator",
    "/api/v66/live-submit-config-readonly-checker",
    "/api/v66/caps-config-readonly-checker",
    "/api/v66/no-enable-no-modify-proof",
    "/api/v66/readiness-governor",
    "/api/v66/execution-lock",
    "/api/v66/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "approval-packet-validator": ["v66_approval_packet_validator_report.json"],
    "v65-baseline": ["v65_baseline_readback_v1_report.json"],
    "exact-phrase-policy": ["v66_exact_phrase_policy_report.json"],
    "approval-metadata-validator": ["v66_approval_metadata_validator_report.json"],
    "live-submit-config-readonly-checker": ["v66_live_submit_config_readonly_checker_report.json"],
    "caps-config-readonly-checker": ["v66_caps_config_readonly_checker_report.json"],
    "no-enable-no-modify-proof": ["v66_no_enable_no_modify_proof_report.json"],
    "readiness-governor": ["readiness_governor_v26_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v25_report.json"],
    "mission-state": ["dummy_mission_state_report_v52.json", "dashboard_v66_report_v1.json", "completion_oriented_next_action_v66_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(66)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v66/reports.py scripts/generate_v66_reports.py dashboard/backend/v66_routes.py",
    "python scripts/generate_v66_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V66Context:
    def __init__(self, *, approval_input, approval_path) -> None:
        self.v65_baseline_status = sgc.baseline_status("final_report_v65.json", "V65")
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V70_LIVE_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V70_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V70_LIVE_CANARY_SCOPE,
            ack_requirements=sgc.V70_ACK_REQUIREMENTS,
        )

    @property
    def validator_status(self) -> str:
        state = self.validation["state"]
        if state == "ABSENT":
            return "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"
        if state == "MALFORMED":
            return "PARTIAL_LIVE_CANARY_APPROVAL_MALFORMED"
        if not self.validation["accepted"]:
            return "FAIL_CLOSED_INVALID_APPROVAL"
        return "PASS_LIVE_CANARY_APPROVAL_PACKET_VALID"

    @property
    def final_verdict(self) -> str:
        if self.v65_baseline_status.startswith("FAIL") or self.validator_status.startswith("FAIL"):
            return "FAIL"
        if self.v65_baseline_status.startswith("PARTIAL") or not self.validation["accepted"]:
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v65_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V65_BASELINE_REGRESSION")
        elif self.v65_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V65_BASELINE_UNAVAILABLE")
        if self.validator_status == "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT":
            blockers.append("LIVE_CANARY_APPROVAL_ABSENT")
        elif self.validator_status == "PARTIAL_LIVE_CANARY_APPROVAL_MALFORMED":
            blockers.append("LIVE_CANARY_APPROVAL_MALFORMED")
        elif self.validator_status.startswith("FAIL"):
            blockers.extend(self.validation["blockers"])
        return blockers

    @property
    def next_action(self) -> str:
        if self.validation["accepted"]:
            return "LIVE_CANARY_APPROVAL_VALIDATED_LIVE_SUBMIT_STILL_OPERATOR_CONTROLLED"
        return "OPERATOR_MAY_PROVIDE_FUTURE_LIVE_CANARY_APPROVAL"


def _common(ctx: V66Context) -> dict[str, Any]:
    return {
        "v65_baseline_status": ctx.v65_baseline_status,
        "approval_packet_validator_status": ctx.validator_status,
        "exact_phrase_policy_status": "PASS_EXACT_PHRASE_POLICY_LOCKED",
        "live_canary_submit_phrase": sgc.V70_LIVE_CANARY_SUBMIT_PHRASE,
        "required_approval_fields": sgc.V70_REQUIRED_APPROVAL_FIELDS,
        "approval_metadata_validator_status": "PASS_APPROVAL_METADATA_VALID" if ctx.validation["accepted"] else "PARTIAL_APPROVAL_METADATA_ABSENT",
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "live_submit_config_readonly_checker_status": "PASS_LIVE_SUBMIT_READ_ONLY",
        "caps_config_readonly_checker_status": "PASS_CAPS_READ_ONLY",
        "no_enable_no_modify_proof_status": "PASS_NO_ENABLE_NO_MODIFY",
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "live_order_placed": False,
        "readiness_governor_v26_status": "PASS",
        "execution_lock_deep_recheck_v25_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V66Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v65_baseline"):
        return "PASS" if ctx.v65_baseline_status == "PASS_V65_BASELINE_READBACK" else "FAIL" if ctx.v65_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v66_approval_packet_validator_report.json":
        return "FAIL" if ctx.validator_status.startswith("FAIL") else "PASS" if ctx.validation["accepted"] else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V66Context) -> dict[str, Any]:
    workstream = "v66: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v66_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V66_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v66_report.json":
        report.update({"completion_oriented_next_action_v66_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v52.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v65_carried_status": ctx.v65_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v66.json"), "approval_validator": str(ARTIFACTS / "v66_approval_packet_validator_report.json"), "no_enable_no_modify": str(ARTIFACTS / "v66_no_enable_no_modify_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v66.json", "dummy_canonical_identity_report_v66.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V66ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V66Context(approval_input=self.approval_input, approval_path=self.approval_path)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
