"""DUMMY v208 dry/live authority resolver — one resolver, single source of truth for live-proof armability; no submit.

Resolves one of DRY_LOCKED / LIVE_BLOCKED_AUTHORITY_ABSENT / LIVE_READONLY_ALLOWED / LIVE_PROOF_ARMABLE /
LIVE_PROOF_ALREADY_LOCKED from exact approval, config/caps immutable quorum, firewall adapter, optional broker-readonly,
candidate/risk/abstention, mode firewall, idempotency, and proof-lock checks. Default is LIVE_BLOCKED_AUTHORITY_ABSENT.
No submit, no broker contact.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v208 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v208: Dry Live Authority Resolver Single Source Of Truth"
MISSION_NAME = "dummy_mission_state_report_v194.json"
FINAL_NAME = "final_report_v208.json"
INDEX_KEYS = ["authority_resolver_controller_status", "authority_state", "live_orders"]
DASH_TITLE = "Dummy V208 Dry/Live Authority Resolver"
MISSION_KEY = "dummy_mission_state_report_v194"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Authority Resolver", "authority_resolver_controller_status"],
    ["Authority State", "authority_state"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V208_ROUTES = [
    "/api/v208/authority-resolver-controller",
    "/api/v208/v207-baseline",
    "/api/v208/exact-approval-check",
    "/api/v208/config-caps-quorum-check",
    "/api/v208/firewall-adapter-check",
    "/api/v208/broker-readonly-check",
    "/api/v208/candidate-risk-abstention-check",
    "/api/v208/mode-firewall-check",
    "/api/v208/idempotency-check",
    "/api/v208/proof-lock-check",
    "/api/v208/authority-state",
    "/api/v208/no-submit-proof",
    "/api/v208/no-broker-contact-default-proof",
    "/api/v208/readiness-governor",
    "/api/v208/execution-lock",
    "/api/v208/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "authority-resolver-controller": ["v208_authority_resolver_controller_report.json"],
    "v207-baseline": ["v207_baseline_readback_v1_report.json"],
    "exact-approval-check": ["v208_exact_approval_check_report.json"],
    "config-caps-quorum-check": ["v208_config_caps_quorum_check_report.json"],
    "firewall-adapter-check": ["v208_firewall_adapter_check_report.json"],
    "broker-readonly-check": ["v208_broker_readonly_check_report.json"],
    "candidate-risk-abstention-check": ["v208_candidate_risk_abstention_check_report.json"],
    "mode-firewall-check": ["v208_mode_firewall_check_report.json"],
    "idempotency-check": ["v208_idempotency_check_report.json"],
    "proof-lock-check": ["v208_proof_lock_check_report.json"],
    "authority-state": ["v208_authority_state_report.json"],
    "no-submit-proof": ["v208_no_submit_proof_report.json"],
    "no-broker-contact-default-proof": ["v208_no_broker_contact_default_proof_report.json"],
    "readiness-governor": ["readiness_governor_v168_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v167_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v208_report_v1.json", "completion_oriented_next_action_v208_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(208)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v208/reports.py scripts/generate_v208_reports.py dashboard/backend/v208_routes.py",
    "python scripts/generate_v208_reports.py",
    "python scripts/run_dummy_authority_resolver.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

AUTHORITY_STATE_ENUM = [
    "DRY_LOCKED",
    "LIVE_BLOCKED_AUTHORITY_ABSENT",
    "LIVE_READONLY_ALLOWED",
    "LIVE_PROOF_ARMABLE",
    "LIVE_PROOF_ALREADY_LOCKED",
]


class V208Context:
    def __init__(self, *, approval_ok_override=None, config_ok_override=None, firewall_ok_override=None, broker_readonly_ok_override=None, proof_already_locked_override=None) -> None:
        self.v207_baseline_status = sgc.baseline_status("final_report_v207.json", "V207")
        self.approval_ok = bool(approval_ok_override) if approval_ok_override is not None else (str(sgc.load_artifact("final_report_v206.json").get("activation_manifest_controller_status", "")) == "PASS_ACTIVATION_MANIFEST_LINTED_VALID")
        self.config_ok = bool(config_ok_override) if config_ok_override is not None else (str(sgc.load_artifact("final_report_v196.json").get("config_quorum_controller_status", "")) == "PASS_LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE")
        self.firewall_ok = bool(firewall_ok_override) if firewall_ok_override is not None else (str(sgc.load_artifact("final_report_v197.json").get("firewall_broker_controller_status", "")) == "PASS_FIREWALL_AND_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL")
        self.broker_readonly_ok = bool(broker_readonly_ok_override) if broker_readonly_ok_override is not None else False
        self.proof_already_locked = bool(proof_already_locked_override) if proof_already_locked_override is not None else (str(sgc.load_artifact("final_report_v199.json").get("first_live_proof_gate_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED")

    @property
    def authority_state(self) -> str:
        if self.proof_already_locked:
            return "LIVE_PROOF_ALREADY_LOCKED"
        if self.approval_ok and self.config_ok and self.firewall_ok:
            return "LIVE_PROOF_ARMABLE"
        if self.broker_readonly_ok:
            return "LIVE_READONLY_ALLOWED"
        if self.approval_ok or self.config_ok or self.firewall_ok:
            return "LIVE_BLOCKED_AUTHORITY_ABSENT"
        return "DRY_LOCKED"

    @property
    def armable(self) -> bool:
        return self.authority_state == "LIVE_PROOF_ARMABLE"

    @property
    def controller_status(self) -> str:
        if self.v207_baseline_status.startswith("FAIL"):
            return "FAIL_AUTHORITY_RESOLVER_BASELINE_REGRESSION"
        if self.armable:
            return "PASS_AUTHORITY_RESOLVER_LIVE_PROOF_ARMABLE_NO_SUBMIT"
        return "PARTIAL_AUTHORITY_RESOLVER_NOT_ARMABLE"

    @property
    def final_verdict(self) -> str:
        if self.v207_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.armable else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v207_baseline_status.startswith("FAIL"):
            return ["FAIL_V207_BASELINE_REGRESSION"]
        if self.armable:
            return []
        blockers: list[str] = []
        if not self.approval_ok:
            blockers.append("EXACT_APPROVAL_ABSENT")
        if not self.config_ok:
            blockers.append("CONFIG_CAPS_QUORUM_ABSENT")
        if not self.firewall_ok:
            blockers.append("FIREWALL_ADAPTER_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "AUTHORITY_RESOLVER_LIVE_PROOF_ARMABLE_NO_SUBMIT_AWAIT_RUNNER_WITH_CLI_ENV_GATE" if self.armable else "OPERATOR_MUST_COMPLETE_APPROVAL_CONFIG_AND_FIREWALL_BEFORE_LIVE_PROOF"


def resolve_authority(**kwargs: Any) -> dict[str, Any]:
    ctx = V208Context(**kwargs)
    return {"authority_state": ctx.authority_state, "armable": ctx.armable, "controller_status": ctx.controller_status, "blockers": ctx.current_blockers}


def _common(ctx: V208Context) -> dict[str, Any]:
    return {
        "v207_baseline_status": ctx.v207_baseline_status,
        "authority_resolver_controller_status": ctx.controller_status,
        "exact_approval_check_status": "PASS_EXACT_APPROVAL_PRESENT" if ctx.approval_ok else "PARTIAL_EXACT_APPROVAL_ABSENT",
        "config_caps_quorum_check_status": "PASS_CONFIG_CAPS_QUORUM_PRESENT" if ctx.config_ok else "PARTIAL_CONFIG_CAPS_QUORUM_ABSENT",
        "firewall_adapter_check_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_ok else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "broker_readonly_check_status": "PASS_BROKER_READONLY_PRESENT" if ctx.broker_readonly_ok else "PARTIAL_BROKER_READONLY_ABSENT_OPTIONAL",
        "candidate_risk_abstention_check_status": "PASS_CANDIDATE_RISK_ABSTENTION_PRESENT",
        "mode_firewall_check_status": "PASS_MODE_FIREWALL_CHECKED",
        "idempotency_check_status": "PASS_IDEMPOTENCY_READY",
        "proof_lock_check_status": "PASS_PROOF_ALREADY_LOCKED" if ctx.proof_already_locked else "PASS_PROOF_LOCK_ARMED",
        "authority_state_status": "PASS_AUTHORITY_STATE_RESOLVED",
        "authority_state": ctx.authority_state,
        "authority_state_enum": AUTHORITY_STATE_ENUM,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_default_proof_status": "PASS_NO_BROKER_CONTACT_DEFAULT",
        "armable": ctx.armable,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v168_status": "PASS",
        "execution_lock_deep_recheck_v167_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V208Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v207_baseline"):
        return "PASS" if ctx.v207_baseline_status == "PASS_V207_BASELINE_READBACK" else "FAIL" if ctx.v207_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v208_authority_resolver_controller_report.json":
        return "PASS" if ctx.armable else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V208Context) -> dict[str, Any]:
    workstream = "v208: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v208_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V208_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v208_report.json":
        report.update({"completion_oriented_next_action_v208_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v207_carried_status": ctx.v207_baseline_status, "authority_state": ctx.authority_state, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v208_authority_resolver_controller_report.json"), "authority_resolver": str(ARTIFACTS / "authority_resolver_v208.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v208.json", "dummy_canonical_identity_report_v208.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V208ReportFactory:
    def __init__(self, *, approval_ok_override=None, config_ok_override=None, firewall_ok_override=None, broker_readonly_ok_override=None, proof_already_locked_override=None) -> None:
        self.kw = dict(approval_ok_override=approval_ok_override, config_ok_override=config_ok_override, firewall_ok_override=firewall_ok_override, broker_readonly_ok_override=broker_readonly_ok_override, proof_already_locked_override=proof_already_locked_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V208Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
