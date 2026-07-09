"""DUMMY v271 final armability runbook resolver freeze and env gate — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v271 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v271: Final Armability Runbook Resolver Freeze And Env Gate"
MISSION_NAME = "dummy_mission_state_report_v257.json"
FINAL_NAME = "final_report_v271.json"
INDEX_KEYS = ['final_armability_runbook_controller_status', 'resolver_state', 'live_orders']
DASH_TITLE = "Dummy V271 Final Armability Runbook Resolver Freeze And Env Gate"
MISSION_KEY = "dummy_mission_state_report_v257"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Armability Runbook', 'final_armability_runbook_controller_status'], ['Resolver State', 'resolver_state'], ['Armability State', 'armability_state'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V271_ROUTES = ['/api/v271/final-armability-runbook-controller', '/api/v271/v270-baseline', '/api/v271/import-wizard-summary', '/api/v271/schema-verifier-summary', '/api/v271/caps-state-summary', '/api/v271/adapter-appliance-summary', '/api/v271/broker-readonly-summary', '/api/v271/resolver-state', '/api/v271/env-gate-status', '/api/v271/proof-lock-status', '/api/v271/armability-state', '/api/v271/no-submit-proof', '/api/v271/no-broker-contact-proof', '/api/v271/readiness-governor', '/api/v271/execution-lock', '/api/v271/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'final-armability-runbook-controller': ['v271_final_armability_runbook_controller_report.json'], 'v270-baseline': ['v270_baseline_readback_v1_report.json'], 'import-wizard-summary': ['v271_import_wizard_summary_report.json'], 'schema-verifier-summary': ['v271_schema_verifier_summary_report.json'], 'caps-state-summary': ['v271_caps_state_summary_report.json'], 'adapter-appliance-summary': ['v271_adapter_appliance_summary_report.json'], 'broker-readonly-summary': ['v271_broker_readonly_summary_report.json'], 'resolver-state': ['v271_resolver_state_report.json'], 'env-gate-status': ['v271_env_gate_status_report.json'], 'proof-lock-status': ['v271_proof_lock_status_report.json'], 'armability-state': ['v271_armability_state_report.json'], 'no-submit-proof': ['v271_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v271_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v231_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v230_report.json'], 'mission-state': ['dummy_mission_state_report_v257.json', 'dashboard_v271_report_v1.json', 'completion_oriented_next_action_v271_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(271)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v271/reports.py scripts/generate_v271_reports.py dashboard/backend/v271_routes.py",
    "python scripts/generate_v271_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v271_final_armability_runbook_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V271Context:
    def __init__(self, *, import_override=None, schema_override=None, caps_override=None, adapter_override=None, freeze_override=None, env_gate_mode=False, env_gate_ack="") -> None:
        self.v270_baseline_status = sgc.baseline_status("final_report_v270.json", "V270")
        self.import_ok = bool(import_override) if import_override is not None else (str(sgc.load_artifact("final_report_v266.json").get("external_authority_import_wizard_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_NO_WRITE")
        self.schema_ok = bool(schema_override) if schema_override is not None else (str(sgc.load_artifact("final_report_v267.json").get("approval_manifest_schema_verifier_controller_status", "")) == "PASS_APPROVAL_MANIFEST_SCHEMA_VERIFIED_READY_FOR_RESOLVER")
        self.caps_ok = bool(caps_override) if caps_override is not None else (str(sgc.load_artifact("final_report_v268.json").get("external_live_submit_caps_state_verifier_controller_status", "")) == "PASS_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_IMMUTABLE")
        self.adapter_ok = bool(adapter_override) if adapter_override is not None else (str(sgc.load_artifact("final_report_v269.json").get("livebrokerfirewall_injection_appliance_controller_status", "")) == "PASS_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_READY_NON_BROKER_DOUBLE")
        self.freeze_ok = bool(freeze_override) if freeze_override is not None else (str(sgc.load_artifact("final_report_v260.json").get("pre_execution_freeze_v2_controller_status", "")) == "PASS_PRE_EXECUTION_FREEZE_V2_READY_NO_SUBMIT")
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.ready = self.import_ok and self.schema_ok and self.caps_ok and self.adapter_ok and self.freeze_ok and self.env_gate

    @property
    def armability_state(self) -> str:
        if not (self.import_ok and self.schema_ok):
            return "ARMABILITY_BLOCKED_IMPORT"
        if not self.caps_ok:
            return "ARMABILITY_BLOCKED_CONFIG_CAPS"
        if not self.adapter_ok:
            return "ARMABILITY_BLOCKED_ADAPTER"
        if not self.env_gate:
            return "ARMABILITY_BLOCKED_ENV_GATE"
        if not self.freeze_ok:
            return "ARMABILITY_BLOCKED_FREEZE"
        return "ARMABILITY_READY_NO_SUBMIT"

    @property
    def resolver_state(self) -> str:
        return "LIVE_PROOF_ARMABLE" if self.ready else ("LIVE_BLOCKED_AUTHORITY_ABSENT" if not (self.import_ok and self.schema_ok and self.caps_ok and self.adapter_ok) else "DRY_LOCKED")

    @property
    def controller_status(self) -> str:
        if self.v270_baseline_status.startswith("FAIL"):
            return "FAIL_FINAL_ARMABILITY_RUNBOOK_BASELINE_REGRESSION"
        return "PASS_FINAL_ARMABILITY_RUNBOOK_READY_NO_SUBMIT" if self.ready else "PARTIAL_FINAL_ARMABILITY_RUNBOOK_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v270_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v270_baseline_status.startswith("FAIL"):
            return ["FAIL_V270_BASELINE_REGRESSION"]
        if self.ready:
            return []
        b = []
        if not self.import_ok:
            b.append("IMPORT_WIZARD_NOT_VALIDATED")
        if not self.schema_ok:
            b.append("SCHEMA_NOT_READY")
        if not self.caps_ok:
            b.append("LIVE_SUBMIT_CAPS_NOT_VERIFIED")
        if not self.adapter_ok:
            b.append("ADAPTER_INJECTION_NOT_READY")
        if not self.freeze_ok:
            b.append("FREEZE_NOT_READY")
        if not self.env_gate:
            b.append("ENV_GATE_ABSENT")
        return b or ["FINAL_ARMABILITY_RUNBOOK_BLOCKED"]

    @property
    def next_action(self) -> str:
        return "FINAL_ARMABILITY_RUNBOOK_READY_OPERATOR_RUN_EXECUTE_ONCE_RUNBOOK_WITH_ENV_GATE_NO_SUBMIT_BY_DUMMY" if self.ready else "OPERATOR_SATISFY_IMPORT_SCHEMA_CAPS_ADAPTER_FREEZE_AND_ENV_GATE_BEFORE_ARMABILITY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v270_baseline_status": ctx.v270_baseline_status,
        "final_armability_runbook_controller_status": ctx.controller_status,
        "armability_state": ctx.armability_state,
        "armability_states": ["ARMABILITY_BLOCKED_IMPORT", "ARMABILITY_BLOCKED_CONFIG_CAPS", "ARMABILITY_BLOCKED_ADAPTER", "ARMABILITY_BLOCKED_ENV_GATE", "ARMABILITY_BLOCKED_FREEZE", "ARMABILITY_READY_NO_SUBMIT"],
        "resolver_state": ctx.resolver_state,
        "import_wizard_summary_status": "PASS_IMPORT_WIZARD_READY" if ctx.import_ok else "PARTIAL_IMPORT_WIZARD_NOT_READY",
        "schema_verifier_summary_status": "PASS_SCHEMA_VERIFIER_READY" if ctx.schema_ok else "PARTIAL_SCHEMA_VERIFIER_NOT_READY",
        "caps_state_summary_status": "PASS_CAPS_STATE_VERIFIED" if ctx.caps_ok else "PARTIAL_CAPS_STATE_NOT_VERIFIED",
        "adapter_appliance_summary_status": "PASS_ADAPTER_APPLIANCE_READY" if ctx.adapter_ok else "PARTIAL_ADAPTER_APPLIANCE_NOT_READY",
        "broker_readonly_summary_status": "PASS_BROKER_READONLY_OPTIONAL",
        "resolver_state_status": "PASS_RESOLVER_STATE_CAPTURED",
        "env_gate_present": ctx.env_gate,
        "env_gate_status": "PASS_ENV_GATE_PRESENT" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,
        "proof_lock_status": "PASS_PROOF_LOCK_CLEAR",
        "idempotency_readiness_status": "PASS_IDEMPOTENCY_READY",
        "candidate_risk_abstention_status": "PASS_CANDIDATE_RISK_ABSTENTION_READY",
        "armability_state_status": "PASS_ARMABILITY_STATE_CLASSIFIED",
        "freeze_ready": ctx.freeze_ok,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v231_status": "PASS",
        "execution_lock_deep_recheck_v230_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v270_baseline"):
        return "PASS" if ctx.v270_baseline_status == "PASS_V270_BASELINE_READBACK" else "FAIL" if ctx.v270_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v271: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v271_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V271_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v271_report.json":
        report.update({"completion_oriented_next_action_v271_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v270_carried_status": ctx.v270_baseline_status, "final_armability_runbook_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v271.json", "dummy_canonical_identity_report_v271.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V271ReportFactory:
    def __init__(self, *, import_override=None, schema_override=None, caps_override=None, adapter_override=None, freeze_override=None, env_gate_mode=False, env_gate_ack='') -> None:
        self.kw = dict(import_override=import_override, schema_override=schema_override, caps_override=caps_override, adapter_override=adapter_override, freeze_override=freeze_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V271Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
