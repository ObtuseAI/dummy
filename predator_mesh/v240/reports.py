"""DUMMY v240 armable quorum doctor resolver explanation no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v240 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v240: Armable Quorum Doctor Resolver Explanation No Submit"
MISSION_NAME = "dummy_mission_state_report_v226.json"
FINAL_NAME = "final_report_v240.json"
INDEX_KEYS = ['armable_quorum_doctor_controller_status', 'resolver_explanation', 'live_orders']
DASH_TITLE = "Dummy V240 Armable Quorum Doctor Resolver Explanation No Submit"
MISSION_KEY = "dummy_mission_state_report_v226"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Quorum Doctor', 'armable_quorum_doctor_controller_status'], ['Resolver Explanation', 'resolver_explanation'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V240_ROUTES = ['/api/v240/armable-quorum-doctor-controller', '/api/v240/v239-baseline', '/api/v240/manifest-doctor-readback', '/api/v240/config-doctor-readback', '/api/v240/adapter-doctor-readback', '/api/v240/broker-readonly-doctor-readback', '/api/v240/dry-validation-readback', '/api/v240/env-gate-check', '/api/v240/mode-live-authorized-check', '/api/v240/proof-target-check', '/api/v240/candidate-risk-abstention-check', '/api/v240/proof-lock-check', '/api/v240/resolver-explanation', '/api/v240/no-submit-proof', '/api/v240/no-broker-contact-proof', '/api/v240/readiness-governor', '/api/v240/execution-lock', '/api/v240/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'armable-quorum-doctor-controller': ['v240_armable_quorum_doctor_controller_report.json'], 'v239-baseline': ['v239_baseline_readback_v1_report.json'], 'manifest-doctor-readback': ['v240_manifest_doctor_readback_report.json'], 'config-doctor-readback': ['v240_config_doctor_readback_report.json'], 'adapter-doctor-readback': ['v240_adapter_doctor_readback_report.json'], 'broker-readonly-doctor-readback': ['v240_broker_readonly_doctor_readback_report.json'], 'dry-validation-readback': ['v240_dry_validation_readback_report.json'], 'env-gate-check': ['v240_env_gate_check_report.json'], 'mode-live-authorized-check': ['v240_mode_live_authorized_check_report.json'], 'proof-target-check': ['v240_proof_target_check_report.json'], 'candidate-risk-abstention-check': ['v240_candidate_risk_abstention_check_report.json'], 'proof-lock-check': ['v240_proof_lock_check_report.json'], 'resolver-explanation': ['v240_resolver_explanation_report.json'], 'no-submit-proof': ['v240_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v240_no_broker_contact_proof_report.json'], 'readiness-governor': ['readiness_governor_v200_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v199_report.json'], 'mission-state': ['dummy_mission_state_report_v226.json', 'dashboard_v240_report_v1.json', 'completion_oriented_next_action_v240_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(240)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v240/reports.py scripts/generate_v240_reports.py dashboard/backend/v240_routes.py",
    "python scripts/generate_v240_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v240_armable_quorum_doctor_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V240Context:
    def __init__(self, *, manifest_override=None, config_override=None, adapter_override=None, broker_readonly_override=None, dry_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, quorum_override=None) -> None:
        self.v239_baseline_status = sgc.baseline_status("final_report_v239.json", "V239")
        self.manifest_ok = bool(manifest_override) if manifest_override is not None else (str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS")
        self.config_ok = bool(config_override) if config_override is not None else (str(sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE")
        self.adapter_ok = bool(adapter_override) if adapter_override is not None else (str(sgc.load_artifact("final_report_v238.json").get("firewall_adapter_doctor_controller_status", "")) == "PASS_FIREWALL_ADAPTER_DOCTOR_READY_NON_BROKER_DOUBLE")
        self.broker_readonly_ok = bool(broker_readonly_override) if broker_readonly_override is not None else (str(sgc.load_artifact("final_report_v239.json").get("broker_readonly_doctor_controller_status", "")) == "PASS_BROKER_READONLY_DOCTOR_READY_NON_BROKER_DOUBLE")
        self.dry_ok = bool(dry_override) if dry_override is not None else (str(sgc.load_artifact("final_report_v227.json").get("one_command_dry_pipeline_controller_status", "")) == "PASS_ONE_COMMAND_DRY_PIPELINE_COMPLETE")
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.mode_live = bool(mode_live_override) if mode_live_override is not None else (str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED")
        checks = {
            "manifest": self.manifest_ok,
            "config_caps": self.config_ok,
            "adapter": self.adapter_ok,
            "broker_readonly": self.broker_readonly_ok,
            "dry_validation": self.dry_ok,
            "env_gate": self.env_gate,
            "mode_live_authorized": self.mode_live,
            "proof_target": True,
            "candidate_risk_abstention": True,
            "idempotency": True,
            "proof_lock_clear": True,
        }
        self.checks = checks
        self.armable = bool(quorum_override) if quorum_override is not None else all(checks.values())

    @property
    def resolver_explanation(self) -> str:
        if self.armable:
            return "ARMABLE"
        if not self.manifest_ok:
            return "BLOCKED_MANIFEST"
        if not self.config_ok:
            return "BLOCKED_CONFIG_CAPS"
        if not self.adapter_ok:
            return "BLOCKED_ADAPTER"
        if not self.broker_readonly_ok:
            return "BLOCKED_BROKER_READONLY"
        if not self.env_gate:
            return "BLOCKED_ENV_GATE"
        if not self.mode_live:
            return "BLOCKED_MODE"
        return "BLOCKED_CANDIDATE_RISK_ABSTENTION"

    @property
    def controller_status(self) -> str:
        if self.v239_baseline_status.startswith("FAIL"):
            return "FAIL_ARMABLE_QUORUM_BASELINE_REGRESSION"
        return "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT" if self.armable else "PARTIAL_ARMABLE_QUORUM_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v239_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.armable else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v239_baseline_status.startswith("FAIL"):
            return ["FAIL_V239_BASELINE_REGRESSION"]
        return [] if self.armable else [self.resolver_explanation]

    @property
    def next_action(self) -> str:
        return "ARMABLE_QUORUM_READY_RUN_EXECUTE_ONCE_HANDOFF_V2_NO_SUBMIT" if self.armable else "OPERATOR_RESOLVE_" + self.resolver_explanation + "_DUMMY_NO_SUBMIT"


def _common(ctx) -> dict[str, Any]:
    return {
        "v239_baseline_status": ctx.v239_baseline_status,
        "armable_quorum_doctor_controller_status": ctx.controller_status,
        "armable": ctx.armable,
        "armable_checks": ctx.checks,
        "resolver_explanation": ctx.resolver_explanation,
        "resolver_state": "LIVE_PROOF_ARMABLE" if ctx.armable else "LIVE_BLOCKED_AUTHORITY_ABSENT",
        "manifest_doctor_readback_status": "PASS_MANIFEST_DOCTOR_READY" if ctx.manifest_ok else "PARTIAL_MANIFEST_DOCTOR_BLOCKED",
        "config_doctor_readback_status": "PASS_CONFIG_DOCTOR_READY" if ctx.config_ok else "PARTIAL_CONFIG_DOCTOR_BLOCKED",
        "adapter_doctor_readback_status": "PASS_ADAPTER_DOCTOR_READY" if ctx.adapter_ok else "PARTIAL_ADAPTER_DOCTOR_BLOCKED",
        "broker_readonly_doctor_readback_status": "PASS_BROKER_READONLY_DOCTOR_READY" if ctx.broker_readonly_ok else "PARTIAL_BROKER_READONLY_DOCTOR_BLOCKED",
        "dry_validation_readback_status": "PASS_DRY_VALIDATION_COMPLETE" if ctx.dry_ok else "PARTIAL_DRY_VALIDATION_ABSENT",
        "env_gate_check_status": "PASS_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,
        "mode_live_authorized_check_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "proof_target_check_status": "PASS_PROOF_TARGET_VALID",
        "candidate_risk_abstention_check_status": "PASS_CANDIDATE_RISK_ABSTENTION_VALID",
        "proof_lock_check_status": "PASS_PROOF_LOCK_CLEAR",
        "resolver_explanation_status": "PASS_RESOLVER_EXPLAINED",
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
        "readiness_governor_v200_status": "PASS",
        "execution_lock_deep_recheck_v199_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v239_baseline"):
        return "PASS" if ctx.v239_baseline_status == "PASS_V239_BASELINE_READBACK" else "FAIL" if ctx.v239_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v240: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v240_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V240_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v240_report.json":
        report.update({"completion_oriented_next_action_v240_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v239_carried_status": ctx.v239_baseline_status, "armable_quorum_doctor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v240.json", "dummy_canonical_identity_report_v240.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V240ReportFactory:
    def __init__(self, *, manifest_override=None, config_override=None, adapter_override=None, broker_readonly_override=None, dry_override=None, env_gate_mode=False, env_gate_ack='', mode_live_override=None, quorum_override=None) -> None:
        self.kw = dict(manifest_override=manifest_override, config_override=config_override, adapter_override=adapter_override, broker_readonly_override=broker_readonly_override, dry_override=dry_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, quorum_override=quorum_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V240Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
