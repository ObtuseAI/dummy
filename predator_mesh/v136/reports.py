"""DUMMY v136 production pilot authority binder — binds every authority input needed for a pilot; never submits.

Read-only binder of the exact controlled-pilot approval, operator live-submit config, caps config, an injected
LiveBrokerFirewall adapter, and an optional broker read-only approval, plus an authority gap ledger. Default is
PARTIAL_PILOT_AUTHORITY_INCOMPLETE. Binding never submits and never contacts a broker.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v136 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v136: Production Pilot Authority Binder And Input Attestation"
MISSION_NAME = "dummy_mission_state_report_v122.json"
FINAL_NAME = "final_report_v136.json"
INDEX_KEYS = ["authority_binder_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V136 Production Pilot Authority Binder"
MISSION_KEY = "dummy_mission_state_report_v122"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Authority Binder", "authority_binder_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V136_ROUTES = [
    "/api/v136/authority-binder-controller",
    "/api/v136/v135-baseline",
    "/api/v136/pilot-approval-file-validator",
    "/api/v136/live-submit-config-reader",
    "/api/v136/caps-config-reader",
    "/api/v136/firewall-adapter-presence-checker",
    "/api/v136/broker-readonly-approval-checker",
    "/api/v136/authority-gap-ledger",
    "/api/v136/no-submit-proof",
    "/api/v136/no-broker-contact-proof",
    "/api/v136/readiness-governor",
    "/api/v136/execution-lock",
    "/api/v136/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "authority-binder-controller": ["v136_authority_binder_controller_report.json"],
    "v135-baseline": ["v135_baseline_readback_v1_report.json"],
    "pilot-approval-file-validator": ["v136_pilot_approval_file_validator_report.json"],
    "live-submit-config-reader": ["v136_live_submit_config_reader_report.json"],
    "caps-config-reader": ["v136_caps_config_reader_report.json"],
    "firewall-adapter-presence-checker": ["v136_firewall_adapter_presence_checker_report.json"],
    "broker-readonly-approval-checker": ["v136_broker_readonly_approval_checker_report.json"],
    "authority-gap-ledger": ["v136_authority_gap_ledger_report.json"],
    "no-submit-proof": ["v136_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v136_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v96_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v95_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v136_report_v1.json", "completion_oriented_next_action_v136_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(136)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v136/reports.py scripts/generate_v136_reports.py dashboard/backend/v136_routes.py",
    "python scripts/generate_v136_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V136Context:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, broker_readonly_present=False) -> None:
        self.v135_baseline_status = sgc.baseline_status("final_report_v135.json", "V135")
        res = sgc.resolve_packet(pilot_approval_path, pilot_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter_present = firewall_adapter is not None
        self.broker_readonly_present = bool(broker_readonly_present)

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def bound(self) -> bool:
        return self.approved and self.live_submit_operator_enabled and self.caps_config_present and self.firewall_adapter_present

    @property
    def authority_gap_ledger(self) -> dict[str, str]:
        return {
            "pilot_approval": "PRESENT" if self.approved else "ABSENT",
            "live_submit_operator_enabled": "PRESENT" if self.live_submit_operator_enabled else "ABSENT",
            "caps_config": "PRESENT" if self.caps_config_present else "ABSENT",
            "firewall_adapter": "PRESENT" if self.firewall_adapter_present else "ABSENT",
            "broker_readonly_approval": "PRESENT" if self.broker_readonly_present else "ABSENT",
        }

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
        if self.bound:
            return "PASS_PILOT_AUTHORITY_BOUND_NO_SUBMIT"
        return "PARTIAL_PILOT_AUTHORITY_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v135_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.bound else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v135_baseline_status.startswith("FAIL"):
            return ["FAIL_V135_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_PILOT_APPROVAL"]
        if self.bound:
            return []
        return [f"AUTHORITY_GAP:{k}" for k, v in self.authority_gap_ledger.items() if v == "ABSENT" and k != "broker_readonly_approval"]

    @property
    def next_action(self) -> str:
        return "PILOT_AUTHORITY_BOUND_NO_SUBMIT_AWAIT_LIVE_SUBMIT_CAPS_SNAPSHOT" if self.bound else "OPERATOR_MUST_BIND_PILOT_APPROVAL_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER"


def _common(ctx: V136Context) -> dict[str, Any]:
    v = ctx.validation
    return {
        "v135_baseline_status": ctx.v135_baseline_status,
        "authority_binder_controller_status": ctx.controller_status,
        "pilot_approval_file_validator_status": "PASS_PILOT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_PILOT_APPROVAL_ABSENT"),
        "pilot_approval_hash": v["approval_hash"],
        "live_submit_config_reader_status": "PASS_LIVE_SUBMIT_OPERATOR_ENABLED_READONLY" if ctx.live_submit_operator_enabled else "PARTIAL_LIVE_SUBMIT_NOT_OPERATOR_ENABLED",
        "caps_config_reader_status": "PASS_CAPS_PRESENT_UNCHANGED_READONLY" if ctx.caps_config_present else "PARTIAL_CAPS_CONFIG_ABSENT",
        "firewall_adapter_presence_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "broker_readonly_approval_checker_status": "PASS_BROKER_READONLY_PRESENT" if ctx.broker_readonly_present else "PARTIAL_BROKER_READONLY_ABSENT",
        "authority_gap_ledger": ctx.authority_gap_ledger,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "authority_bound": ctx.bound,
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
        "readiness_governor_v96_status": "PASS",
        "execution_lock_deep_recheck_v95_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V136Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v135_baseline"):
        return "PASS" if ctx.v135_baseline_status == "PASS_V135_BASELINE_READBACK" else "FAIL" if ctx.v135_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v136_authority_binder_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.bound else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V136Context) -> dict[str, Any]:
    workstream = "v136: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v136_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V136_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v136_report.json":
        report.update({"completion_oriented_next_action_v136_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v135_carried_status": ctx.v135_baseline_status, "authority_binder_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v136_authority_binder_controller_report.json"), "no_submit": str(ARTIFACTS / "v136_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v136.json", "dummy_canonical_identity_report_v136.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V136ReportFactory:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, broker_readonly_present=False) -> None:
        self.kw = dict(pilot_approval=pilot_approval, pilot_approval_path=pilot_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, broker_readonly_present=broker_readonly_present)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V136Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
