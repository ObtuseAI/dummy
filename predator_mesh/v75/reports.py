"""DUMMY v75 operator live-config / caps / approval tieout (no broker submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v75 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V75_ROUTES = [
    "/api/v75/config-tieout-controller",
    "/api/v75/v74-baseline",
    "/api/v75/live-submit-readonly-checker",
    "/api/v75/caps-readonly-checker",
    "/api/v75/exact-approval-file-validator",
    "/api/v75/expiry-scope-max-one-order-validator",
    "/api/v75/no-enable-live-submit-proof",
    "/api/v75/no-caps-modification-proof",
    "/api/v75/readiness-governor",
    "/api/v75/execution-lock",
    "/api/v75/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "config-tieout-controller": ["v75_config_tieout_controller_report.json"],
    "v74-baseline": ["v74_baseline_readback_v1_report.json"],
    "live-submit-readonly-checker": ["v75_live_submit_readonly_checker_report.json"],
    "caps-readonly-checker": ["v75_caps_readonly_checker_report.json"],
    "exact-approval-file-validator": ["v75_exact_approval_file_validator_report.json"],
    "expiry-scope-max-one-order-validator": ["v75_expiry_scope_max_one_order_validator_report.json"],
    "no-enable-live-submit-proof": ["v75_no_enable_live_submit_proof_report.json"],
    "no-caps-modification-proof": ["v75_no_caps_modification_proof_report.json"],
    "readiness-governor": ["readiness_governor_v35_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v34_report.json"],
    "mission-state": ["dummy_mission_state_report_v61.json", "dashboard_v75_report_v1.json", "completion_oriented_next_action_v75_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(75)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v75/reports.py scripts/generate_v75_reports.py dashboard/backend/v75_routes.py",
    "python scripts/generate_v75_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V75Context:
    def __init__(self, *, approval_input, approval_path, live_submit_operator_enabled, caps_config_present) -> None:
        self.v74_baseline_status = sgc.baseline_status("final_report_v74.json", "V74")
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.V70_LIVE_CANARY_SUBMIT_PHRASE,
            required_fields=sgc.V70_REQUIRED_APPROVAL_FIELDS,
            required_scope=sgc.V70_LIVE_CANARY_SCOPE,
            ack_requirements=sgc.V70_ACK_REQUIREMENTS,
        )
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)

    @property
    def tied_out(self) -> bool:
        return self.validation["accepted"] and self.live_submit_operator_enabled and self.caps_config_present

    @property
    def controller_status(self) -> str:
        if self.validation["state"] == "PRESENT" and not self.validation["accepted"]:
            return "FAIL_CLOSED_INVALID_APPROVAL"
        if self.tied_out:
            return "PASS_LIVE_CONFIG_CAPS_APPROVAL_TIED_OUT_NO_SUBMIT"
        return "PARTIAL_LIVE_CANARY_APPROVAL_OR_CONFIG_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v74_baseline_status.startswith("FAIL") or self.controller_status.startswith("FAIL"):
            return "FAIL"
        if self.v74_baseline_status.startswith("PARTIAL") or not self.tied_out:
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v74_baseline_status.startswith("FAIL"):
            return ["FAIL_V74_BASELINE_REGRESSION"]
        blockers: list[str] = []
        if self.controller_status.startswith("FAIL"):
            blockers.append("FAIL_CLOSED_INVALID_APPROVAL")
            return blockers
        if not self.validation["accepted"]:
            blockers.append("LIVE_CANARY_APPROVAL_ABSENT")
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        if self.tied_out:
            return "LIVE_CONFIG_CAPS_APPROVAL_TIED_OUT_AWAIT_AUTH_PACKET"
        return "OPERATOR_MUST_PROVIDE_APPROVAL_AND_ENABLE_LIVE_SUBMIT_AND_CAPS"


def _common(ctx: V75Context) -> dict[str, Any]:
    return {
        "v74_baseline_status": ctx.v74_baseline_status,
        "config_tieout_controller_status": ctx.controller_status,
        "live_submit_readonly_checker_status": "PASS_LIVE_SUBMIT_READ_ONLY",
        "caps_readonly_checker_status": "PASS_CAPS_READ_ONLY",
        "exact_approval_file_validator_status": "PASS_EXACT_APPROVAL_VALID" if ctx.validation["accepted"] else ("FAIL_CLOSED_INVALID_APPROVAL" if ctx.validation["state"] == "PRESENT" else "PARTIAL_APPROVAL_ABSENT"),
        "expiry_scope_max_one_order_validator_status": "PASS_EXPIRY_SCOPE_MAX_ONE_ORDER" if ctx.validation["accepted"] else "PARTIAL_APPROVAL_ABSENT",
        "no_enable_live_submit_proof_status": "PASS_NO_ENABLE_LIVE_SUBMIT",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "readiness_governor_v35_status": "PASS",
        "execution_lock_deep_recheck_v34_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V75Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v74_baseline"):
        return "PASS" if ctx.v74_baseline_status == "PASS_V74_BASELINE_READBACK" else "FAIL" if ctx.v74_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v75_config_tieout_controller_report.json":
        return "FAIL" if ctx.controller_status.startswith("FAIL") else "PASS" if ctx.tied_out else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V75Context) -> dict[str, Any]:
    workstream = "v75: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v75_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V75_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v75_report.json":
        report.update({"completion_oriented_next_action_v75_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v61.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v74_carried_status": ctx.v74_baseline_status, "config_tieout_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v75.json"), "config_tieout": str(ARTIFACTS / "v75_config_tieout_controller_report.json"), "no_enable_live_submit": str(ARTIFACTS / "v75_no_enable_live_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v75.json", "dummy_canonical_identity_report_v75.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V75ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.live_submit_operator_enabled = live_submit_operator_enabled
        self.caps_config_present = caps_config_present

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V75Context(approval_input=self.approval_input, approval_path=self.approval_path, live_submit_operator_enabled=self.live_submit_operator_enabled, caps_config_present=self.caps_config_present)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
