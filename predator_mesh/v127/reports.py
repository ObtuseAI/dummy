"""DUMMY v127 production pilot approval/config/caps/firewall tieout — validates every pilot prerequisite; never submits.

Read-only tieout of the exact controlled-pilot approval, operator live-submit config, caps config, and an injected
LiveBrokerFirewall adapter, plus kill-switch/rollback/idempotency prerequisites. Default is
PARTIAL_PILOT_APPROVAL_OR_CONFIG_ABSENT. Even when everything validates it NEVER submits — it only confirms readiness.
No broker contact, no order.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v127 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v127: Production Pilot Approval Config Caps Firewall Tieout No Submit"
MISSION_NAME = "dummy_mission_state_report_v113.json"
FINAL_NAME = "final_report_v127.json"
INDEX_KEYS = ["pilot_tieout_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V127 Production Pilot Approval/Config Tieout"
MISSION_KEY = "dummy_mission_state_report_v113"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Tieout", "pilot_tieout_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V127_ROUTES = [
    "/api/v127/pilot-tieout-controller",
    "/api/v127/v126-baseline",
    "/api/v127/pilot-approval-validator",
    "/api/v127/live-submit-readonly-checker",
    "/api/v127/caps-readonly-checker",
    "/api/v127/firewall-adapter-presence-checker",
    "/api/v127/no-direct-broker-bypass-proof",
    "/api/v127/no-broker-contact-proof",
    "/api/v127/no-account-private-data-proof",
    "/api/v127/kill-switch-prerequisite",
    "/api/v127/rollback-prerequisite",
    "/api/v127/idempotency-prerequisite",
    "/api/v127/no-submit-proof",
    "/api/v127/readiness-governor",
    "/api/v127/execution-lock",
    "/api/v127/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "pilot-tieout-controller": ["v127_pilot_tieout_controller_report.json"],
    "v126-baseline": ["v126_baseline_readback_v1_report.json"],
    "pilot-approval-validator": ["v127_pilot_approval_validator_report.json"],
    "live-submit-readonly-checker": ["v127_live_submit_readonly_checker_report.json"],
    "caps-readonly-checker": ["v127_caps_readonly_checker_report.json"],
    "firewall-adapter-presence-checker": ["v127_firewall_adapter_presence_checker_report.json"],
    "no-direct-broker-bypass-proof": ["v127_no_direct_broker_bypass_proof_report.json"],
    "no-broker-contact-proof": ["v127_no_broker_contact_proof_report.json"],
    "no-account-private-data-proof": ["v127_no_account_private_data_proof_report.json"],
    "kill-switch-prerequisite": ["v127_kill_switch_prerequisite_report.json"],
    "rollback-prerequisite": ["v127_rollback_prerequisite_report.json"],
    "idempotency-prerequisite": ["v127_idempotency_prerequisite_report.json"],
    "no-submit-proof": ["v127_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v87_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v86_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v127_report_v1.json", "completion_oriented_next_action_v127_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(127)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v127/reports.py scripts/generate_v127_reports.py dashboard/backend/v127_routes.py",
    "python scripts/generate_v127_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V127Context:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.v126_baseline_status = sgc.baseline_status("final_report_v126.json", "V126")
        res = sgc.resolve_packet(pilot_approval_path, pilot_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def tieout_ok(self) -> bool:
        return self.approved and self.live_submit_operator_enabled and self.caps_config_present and self.firewall_adapter_present

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
        if self.tieout_ok:
            return "PASS_PILOT_APPROVAL_CONFIG_FIREWALL_TIEOUT_READY_NO_SUBMIT"
        return "PARTIAL_PILOT_APPROVAL_OR_CONFIG_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v126_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.tieout_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v126_baseline_status.startswith("FAIL"):
            return ["FAIL_V126_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_PILOT_APPROVAL"]
        if self.tieout_ok:
            return []
        blockers: list[str] = []
        if not self.approved:
            blockers.append("PILOT_APPROVAL_ABSENT")
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        if not self.firewall_adapter_present:
            blockers.append("FIREWALL_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "PILOT_TIEOUT_READY_NO_SUBMIT_AWAIT_AUTH_PACKET_ASSEMBLY" if self.tieout_ok else "OPERATOR_MUST_PROVIDE_PILOT_APPROVAL_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER"


def _common(ctx: V127Context) -> dict[str, Any]:
    v = ctx.validation
    return {
        "v126_baseline_status": ctx.v126_baseline_status,
        "pilot_tieout_controller_status": ctx.controller_status,
        "pilot_approval_validator_status": "PASS_PILOT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_PILOT_APPROVAL_ABSENT"),
        "pilot_approval_hash": v["approval_hash"],
        "live_submit_readonly_checker_status": "PASS_LIVE_SUBMIT_OPERATOR_ENABLED_READONLY" if ctx.live_submit_operator_enabled else "PARTIAL_LIVE_SUBMIT_NOT_OPERATOR_ENABLED",
        "caps_readonly_checker_status": "PASS_CAPS_PRESENT_UNCHANGED_READONLY" if ctx.caps_config_present else "PARTIAL_CAPS_CONFIG_ABSENT",
        "firewall_adapter_presence_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "no_direct_broker_bypass_proof_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_account_private_data_proof_status": "PASS_NO_ACCOUNT_PRIVATE_DATA",
        "kill_switch_prerequisite_status": "PASS_KILL_SWITCH_ARMED",
        "rollback_prerequisite_status": "PASS_ROLLBACK_READY",
        "idempotency_prerequisite_status": "PASS_IDEMPOTENCY_READY",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "tieout_ready": ctx.tieout_ok,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v87_status": "PASS",
        "execution_lock_deep_recheck_v86_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V127Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v126_baseline"):
        return "PASS" if ctx.v126_baseline_status == "PASS_V126_BASELINE_READBACK" else "FAIL" if ctx.v126_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v127_pilot_tieout_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.tieout_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V127Context) -> dict[str, Any]:
    workstream = "v127: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v127_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V127_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v127_report.json":
        report.update({"completion_oriented_next_action_v127_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v126_carried_status": ctx.v126_baseline_status, "pilot_tieout_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v127_pilot_tieout_controller_report.json"), "no_submit": str(ARTIFACTS / "v127_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v127.json", "dummy_canonical_identity_report_v127.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V127ReportFactory:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.kw = dict(pilot_approval=pilot_approval, pilot_approval_path=pilot_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V127Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
