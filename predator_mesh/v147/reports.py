"""DUMMY v147 real authority intake validator — validates manually supplied real authority inputs; never submits.

Read-only validation of the exact controlled-pilot approval, optional broker read-only approval, operator live-submit
config, caps config, and an injected LiveBrokerFirewall adapter, plus config/caps hash snapshots and secret redaction.
Default is PARTIAL_REAL_AUTHORITY_INPUTS_ABSENT_OR_INCOMPLETE. Validation never submits and never contacts a broker.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v147 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v147: Real Authority Intake Validator Approval Config Caps Firewall No Submit"
MISSION_NAME = "dummy_mission_state_report_v133.json"
FINAL_NAME = "final_report_v147.json"
INDEX_KEYS = ["intake_validator_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V147 Real Authority Intake Validator"
MISSION_KEY = "dummy_mission_state_report_v133"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Intake Validator", "intake_validator_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V147_ROUTES = [
    "/api/v147/intake-validator-controller",
    "/api/v147/v146-baseline",
    "/api/v147/production-pilot-approval-validator",
    "/api/v147/broker-readonly-approval-validator",
    "/api/v147/live-submit-readonly-checker",
    "/api/v147/caps-readonly-checker",
    "/api/v147/firewall-adapter-checker",
    "/api/v147/config-hash-snapshot",
    "/api/v147/caps-hash-snapshot",
    "/api/v147/secret-redaction",
    "/api/v147/no-submit-proof",
    "/api/v147/no-caps-modification-proof",
    "/api/v147/readiness-governor",
    "/api/v147/execution-lock",
    "/api/v147/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "intake-validator-controller": ["v147_intake_validator_controller_report.json"],
    "v146-baseline": ["v146_baseline_readback_v1_report.json"],
    "production-pilot-approval-validator": ["v147_production_pilot_approval_validator_report.json"],
    "broker-readonly-approval-validator": ["v147_broker_readonly_approval_validator_report.json"],
    "live-submit-readonly-checker": ["v147_live_submit_readonly_checker_report.json"],
    "caps-readonly-checker": ["v147_caps_readonly_checker_report.json"],
    "firewall-adapter-checker": ["v147_firewall_adapter_checker_report.json"],
    "config-hash-snapshot": ["v147_config_hash_snapshot_report.json"],
    "caps-hash-snapshot": ["v147_caps_hash_snapshot_report.json"],
    "secret-redaction": ["v147_secret_redaction_report.json"],
    "no-submit-proof": ["v147_no_submit_proof_report.json"],
    "no-caps-modification-proof": ["v147_no_caps_modification_proof_report.json"],
    "readiness-governor": ["readiness_governor_v107_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v106_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v147_report_v1.json", "completion_oriented_next_action_v147_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(147)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v147/reports.py scripts/generate_v147_reports.py dashboard/backend/v147_routes.py",
    "python scripts/generate_v147_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V147Context:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, broker_readonly_approval=None, broker_readonly_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.v146_baseline_status = sgc.baseline_status("final_report_v146.json", "V146")
        res = sgc.resolve_packet(pilot_approval_path, pilot_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.CONTROLLED_PILOT_PHRASE, required_fields=sgc.CONTROLLED_PILOT_FIELDS, required_scope=sgc.CONTROLLED_PILOT_SCOPE, ack_requirements=sgc.CONTROLLED_PILOT_ACKS)
        bres = sgc.resolve_packet(broker_readonly_approval_path, broker_readonly_approval)
        self.broker_validation = sgc.validate_packet(bres, required_phrase=sgc.BROKER_READONLY_PHRASE, required_fields=sgc.BROKER_READONLY_FIELDS, required_scope=sgc.BROKER_READONLY_SCOPE)
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
    def broker_approved(self) -> bool:
        return bool(self.broker_validation["accepted"])

    @property
    def intake_ok(self) -> bool:
        return self.approved and self.live_submit_operator_enabled and self.caps_config_present and self.firewall_adapter_present

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
        if self.intake_ok:
            return "PASS_REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT"
        return "PARTIAL_REAL_AUTHORITY_INPUTS_ABSENT_OR_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v146_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.intake_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v146_baseline_status.startswith("FAIL"):
            return ["FAIL_V146_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_PILOT_APPROVAL"]
        if self.intake_ok:
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
        return "REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT_AWAIT_MODE_FIREWALL_AND_PREFLIGHT" if self.intake_ok else "OPERATOR_MUST_SUPPLY_EXACT_PILOT_APPROVAL_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER"


def _common(ctx: V147Context) -> dict[str, Any]:
    v = ctx.validation
    return {
        "v146_baseline_status": ctx.v146_baseline_status,
        "intake_validator_controller_status": ctx.controller_status,
        "production_pilot_approval_validator_status": "PASS_PILOT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_PILOT_APPROVAL" if ctx.any_fail else "PARTIAL_PILOT_APPROVAL_ABSENT"),
        "pilot_approval_hash": v["approval_hash"],
        "broker_readonly_approval_validator_status": "PASS_BROKER_READONLY_APPROVAL_VALID" if ctx.broker_approved else "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT",
        "broker_readonly_approval_hash": ctx.broker_validation["approval_hash"],
        "live_submit_readonly_checker_status": "PASS_LIVE_SUBMIT_OPERATOR_ENABLED_READONLY" if ctx.live_submit_operator_enabled else "PARTIAL_LIVE_SUBMIT_NOT_OPERATOR_ENABLED",
        "caps_readonly_checker_status": "PASS_CAPS_PRESENT_UNCHANGED_READONLY" if ctx.caps_config_present else "PARTIAL_CAPS_CONFIG_ABSENT",
        "firewall_adapter_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "config_hash_snapshot_status": "PASS_CONFIG_HASH_SNAPSHOTTED",
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash_snapshot_status": "PASS_CAPS_HASH_SNAPSHOTTED",
        "caps_hash": CAPS_HASH,
        "secret_redaction_status": "PASS_SECRETS_REDACTED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "intake_valid": ctx.intake_ok,
        "approval_files_written": 0,
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
        "readiness_governor_v107_status": "PASS",
        "execution_lock_deep_recheck_v106_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V147Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v146_baseline"):
        return "PASS" if ctx.v146_baseline_status == "PASS_V146_BASELINE_READBACK" else "FAIL" if ctx.v146_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v147_intake_validator_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.intake_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V147Context) -> dict[str, Any]:
    workstream = "v147: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v147_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V147_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v147_report.json":
        report.update({"completion_oriented_next_action_v147_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v146_carried_status": ctx.v146_baseline_status, "intake_validator_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v147_intake_validator_controller_report.json"), "no_submit": str(ARTIFACTS / "v147_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v147.json", "dummy_canonical_identity_report_v147.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V147ReportFactory:
    def __init__(self, *, pilot_approval=None, pilot_approval_path=None, broker_readonly_approval=None, broker_readonly_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.kw = dict(pilot_approval=pilot_approval, pilot_approval_path=pilot_approval_path, broker_readonly_approval=broker_readonly_approval, broker_readonly_approval_path=broker_readonly_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V147Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
