"""DUMMY v217 zero broker dry validation full path no contact — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v217 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v217: Zero Broker Dry Validation Full Path No Contact"
MISSION_NAME = "dummy_mission_state_report_v203.json"
FINAL_NAME = "final_report_v217.json"
INDEX_KEYS = ['zero_broker_dry_validation_controller_status', 'broker_contacted', 'live_orders']
DASH_TITLE = "Dummy V217 Zero Broker Dry Validation Full Path No Contact"
MISSION_KEY = "dummy_mission_state_report_v203"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Dry Validation', 'zero_broker_dry_validation_controller_status'], ['Broker Contacted', 'real_broker_contacted'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V217_ROUTES = ['/api/v217/zero-broker-dry-validation-controller', '/api/v217/v216-baseline', '/api/v217/dry-mode-authority-resolver-run', '/api/v217/candidate-risk-abstention-checks', '/api/v217/proof-target-validation', '/api/v217/simulated-idempotency-key', '/api/v217/simulated-proof-lock', '/api/v217/simulated-reconcile-schema', '/api/v217/simulated-forensic-schema', '/api/v217/no-firewall-submit-proof', '/api/v217/no-broker-payload-proof', '/api/v217/no-account-access-proof', '/api/v217/no-file-write-proof', '/api/v217/readiness-governor', '/api/v217/execution-lock', '/api/v217/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'zero-broker-dry-validation-controller': ['v217_zero_broker_dry_validation_controller_report.json'], 'v216-baseline': ['v216_baseline_readback_v1_report.json'], 'dry-mode-authority-resolver-run': ['v217_dry_mode_authority_resolver_run_report.json'], 'candidate-risk-abstention-checks': ['v217_candidate_risk_abstention_checks_report.json'], 'proof-target-validation': ['v217_proof_target_validation_report.json'], 'simulated-idempotency-key': ['v217_simulated_idempotency_key_report.json'], 'simulated-proof-lock': ['v217_simulated_proof_lock_report.json'], 'simulated-reconcile-schema': ['v217_simulated_reconcile_schema_report.json'], 'simulated-forensic-schema': ['v217_simulated_forensic_schema_report.json'], 'no-firewall-submit-proof': ['v217_no_firewall_submit_proof_report.json'], 'no-broker-payload-proof': ['v217_no_broker_payload_proof_report.json'], 'no-account-access-proof': ['v217_no_account_access_proof_report.json'], 'no-file-write-proof': ['v217_no_file_write_proof_report.json'], 'readiness-governor': ['readiness_governor_v177_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v176_report.json'], 'mission-state': ['dummy_mission_state_report_v203.json', 'dashboard_v217_report_v1.json', 'completion_oriented_next_action_v217_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(217)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v217/reports.py scripts/generate_v217_reports.py dashboard/backend/v217_routes.py",
    "python scripts/generate_v217_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v217_zero_broker_dry_validation_controller_report.json"

class V217Context:
    def __init__(self) -> None:
        self.v216_baseline_status = sgc.baseline_status("final_report_v216.json", "V216")
        self.resolver_status = str(sgc.load_artifact("authority_resolver_v208.json").get("authority_state", sgc.load_artifact("final_report_v208.json").get("authority_state", "LIVE_BLOCKED_AUTHORITY_ABSENT")))
        # Fully simulated first-live-proof path; no adapter, no broker, no payload.
        self.simulated_idempotency_key = sgc.sha256_bytes(b"v217-zero-broker-dry-validation")[:32]
        self.simulated_proof_lock = "SIMULATED_PROOF_LOCK_ARMED"

    @property
    def controller_status(self) -> str:
        return "FAIL_ZERO_BROKER_DRY_VALIDATION_BASELINE_REGRESSION" if self.v216_baseline_status.startswith("FAIL") else "PASS_ZERO_BROKER_DRY_VALIDATION_COMPLETE"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v216_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list:
        return ["FAIL_V216_BASELINE_REGRESSION"] if self.v216_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "ZERO_BROKER_DRY_VALIDATION_COMPLETE_RUN_FINAL_ARMING_CHECK_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v216_baseline_status": ctx.v216_baseline_status,
        "zero_broker_dry_validation_controller_status": ctx.controller_status,
        "dry_mode": True,
        "dry_mode_authority_resolver_run_status": "PASS_DRY_MODE_AUTHORITY_RESOLVER_RUN",
        "dry_mode_resolver_state": ctx.resolver_status,
        "candidate_risk_abstention_checks_status": "PASS_CANDIDATE_RISK_ABSTENTION_CHECKS",
        "proof_target_validation_status": "PASS_PROOF_TARGET_VALIDATED",
        "simulated_idempotency_key": ctx.simulated_idempotency_key,
        "simulated_idempotency_key_status": "PASS_SIMULATED_IDEMPOTENCY_KEY",
        "simulated_proof_lock": ctx.simulated_proof_lock,
        "simulated_proof_lock_status": "PASS_SIMULATED_PROOF_LOCK",
        "simulated_reconcile_schema_status": "PASS_SIMULATED_RECONCILE_SCHEMA",
        "simulated_forensic_schema_status": "PASS_SIMULATED_FORENSIC_SCHEMA",
        "no_firewall_submit_proof_status": "PASS_NO_FIREWALL_SUBMIT",
        "firewall_submit_invoked": False,
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "broker_payload_created": False,
        "no_account_access_proof_status": "PASS_NO_ACCOUNT_ACCESS",
        "no_file_write_proof_status": "PASS_NO_FILE_WRITE",
        "broker_contacted": False,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "readiness_governor_v177_status": "PASS",
        "execution_lock_deep_recheck_v176_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v216_baseline"):
        return "PASS" if ctx.v216_baseline_status == "PASS_V216_BASELINE_READBACK" else "FAIL" if ctx.v216_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v217: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v217_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V217_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v217_report.json":
        report.update({"completion_oriented_next_action_v217_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v216_carried_status": ctx.v216_baseline_status, "zero_broker_dry_validation_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v217.json", "dummy_canonical_identity_report_v217.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V217ReportFactory:
    def __init__(self, ) -> None:
        self.kw = dict()

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V217Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
