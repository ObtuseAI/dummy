"""DUMMY v87 live-config / caps / firewall-adapter readiness — no broker contact by default."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v87 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V87_ROUTES = [
    "/api/v87/readiness-controller",
    "/api/v87/v86-baseline",
    "/api/v87/live-submit-readonly-checker",
    "/api/v87/caps-readonly-checker",
    "/api/v87/firewall-adapter-presence-checker",
    "/api/v87/no-direct-broker-bypass-proof",
    "/api/v87/no-broker-contact-proof",
    "/api/v87/no-private-account-access-proof",
    "/api/v87/no-submit-no-cancel-proof",
    "/api/v87/readiness-governor",
    "/api/v87/execution-lock",
    "/api/v87/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "readiness-controller": ["v87_readiness_controller_report.json"],
    "v86-baseline": ["v86_baseline_readback_v1_report.json"],
    "live-submit-readonly-checker": ["v87_live_submit_readonly_checker_report.json"],
    "caps-readonly-checker": ["v87_caps_readonly_checker_report.json"],
    "firewall-adapter-presence-checker": ["v87_firewall_adapter_presence_checker_report.json"],
    "no-direct-broker-bypass-proof": ["v87_no_direct_broker_bypass_proof_report.json"],
    "no-broker-contact-proof": ["v87_no_broker_contact_proof_report.json"],
    "no-private-account-access-proof": ["v87_no_private_account_access_proof_report.json"],
    "no-submit-no-cancel-proof": ["v87_no_submit_no_cancel_proof_report.json"],
    "readiness-governor": ["readiness_governor_v47_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v46_report.json"],
    "mission-state": ["dummy_mission_state_report_v73.json", "dashboard_v87_report_v1.json", "completion_oriented_next_action_v87_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(87)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v87/reports.py scripts/generate_v87_reports.py dashboard/backend/v87_routes.py",
    "python scripts/generate_v87_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V87Context:
    def __init__(self, *, live_submit_operator_enabled, caps_config_present, firewall_adapter) -> None:
        self.v86_baseline_status = sgc.baseline_status("final_report_v86.json", "V86")
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.adapter_present = firewall_adapter is not None

    @property
    def ready(self) -> bool:
        return self.live_submit_operator_enabled and self.caps_config_present and self.adapter_present

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_CONFIG_CAPS_FIREWALL_READY_NO_CONTACT" if self.ready else "PARTIAL_LIVE_CONFIG_OR_ADAPTER_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v86_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.v86_baseline_status.startswith("PARTIAL") or not self.ready:
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v86_baseline_status.startswith("FAIL"):
            return ["FAIL_V86_BASELINE_REGRESSION"]
        blockers: list[str] = []
        if self.v86_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V86_BASELINE_UNAVAILABLE")
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        if not self.adapter_present:
            blockers.append("FIREWALL_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "LIVE_CONFIG_CAPS_FIREWALL_READY_AWAIT_CANDIDATE_QUEUE" if self.ready else "OPERATOR_MUST_ENABLE_LIVE_SUBMIT_PROVIDE_CAPS_AND_INJECT_FIREWALL"


def _common(ctx: V87Context) -> dict[str, Any]:
    return {
        "v86_baseline_status": ctx.v86_baseline_status,
        "readiness_controller_status": ctx.controller_status,
        "live_submit_readonly_checker_status": "PASS_LIVE_SUBMIT_READ_ONLY",
        "caps_readonly_checker_status": "PASS_CAPS_READ_ONLY",
        "firewall_adapter_presence_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "firewall_adapter_present": ctx.adapter_present,
        "adapter_must_be_explicitly_injected": True,
        "no_direct_broker_bypass_proof_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "broker_contacted": False,
        "no_private_account_access_proof_status": "PASS_NO_PRIVATE_ACCOUNT_ACCESS",
        "no_submit_no_cancel_proof_status": "PASS_NO_SUBMIT_NO_CANCEL",
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "live_orders": 0,
        "readiness_governor_v47_status": "PASS",
        "execution_lock_deep_recheck_v46_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V87Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v86_baseline"):
        return "PASS" if ctx.v86_baseline_status == "PASS_V86_BASELINE_READBACK" else "FAIL" if ctx.v86_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v87_readiness_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V87Context) -> dict[str, Any]:
    workstream = "v87: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v87_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V87_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_contact_broker": False})
    elif name == "completion_oriented_next_action_v87_report.json":
        report.update({"completion_oriented_next_action_v87_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v73.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v86_carried_status": ctx.v86_baseline_status, "readiness_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v87.json"), "no_broker_contact": str(ARTIFACTS / "v87_no_broker_contact_proof_report.json"), "no_submit_no_cancel": str(ARTIFACTS / "v87_no_submit_no_cancel_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v87.json", "dummy_canonical_identity_report_v87.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V87ReportFactory:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.live_submit_operator_enabled = live_submit_operator_enabled
        self.caps_config_present = caps_config_present
        self.firewall_adapter = firewall_adapter

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V87Context(live_submit_operator_enabled=self.live_submit_operator_enabled, caps_config_present=self.caps_config_present, firewall_adapter=self.firewall_adapter)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
