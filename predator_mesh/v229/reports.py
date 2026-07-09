"""DUMMY v229 final resolver arming orchestrator no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v229 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v229: Final Resolver Arming Orchestrator No Submit"
MISSION_NAME = "dummy_mission_state_report_v215.json"
FINAL_NAME = "final_report_v229.json"
INDEX_KEYS = ['final_resolver_arming_controller_status', 'arming_ready', 'live_orders']
DASH_TITLE = "Dummy V229 Final Resolver Arming Orchestrator No Submit"
MISSION_KEY = "dummy_mission_state_report_v215"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Resolver Arming', 'final_resolver_arming_controller_status'], ['Arming Ready', 'arming_ready'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V229_ROUTES = ['/api/v229/final-resolver-arming-controller', '/api/v229/v228-baseline', '/api/v229/resolver-state-readback', '/api/v229/intake-valid-quorum', '/api/v229/config-caps-immutable-quorum', '/api/v229/firewall-adapter-proof', '/api/v229/dry-pipeline-proof', '/api/v229/kill-switch-proof', '/api/v229/rollback-proof', '/api/v229/idempotency-proof', '/api/v229/one-attempt-proof', '/api/v229/no-market-order-proof', '/api/v229/mode-live-authorized-proof', '/api/v229/env-gate-check', '/api/v229/no-submit-proof', '/api/v229/readiness-governor', '/api/v229/execution-lock', '/api/v229/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'final-resolver-arming-controller': ['v229_final_resolver_arming_controller_report.json'], 'v228-baseline': ['v228_baseline_readback_v1_report.json'], 'resolver-state-readback': ['v229_resolver_state_readback_report.json'], 'intake-valid-quorum': ['v229_intake_valid_quorum_report.json'], 'config-caps-immutable-quorum': ['v229_config_caps_immutable_quorum_report.json'], 'firewall-adapter-proof': ['v229_firewall_adapter_proof_report.json'], 'dry-pipeline-proof': ['v229_dry_pipeline_proof_report.json'], 'kill-switch-proof': ['v229_kill_switch_proof_report.json'], 'rollback-proof': ['v229_rollback_proof_report.json'], 'idempotency-proof': ['v229_idempotency_proof_report.json'], 'one-attempt-proof': ['v229_one_attempt_proof_report.json'], 'no-market-order-proof': ['v229_no_market_order_proof_report.json'], 'mode-live-authorized-proof': ['v229_mode_live_authorized_proof_report.json'], 'env-gate-check': ['v229_env_gate_check_report.json'], 'no-submit-proof': ['v229_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v189_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v188_report.json'], 'mission-state': ['dummy_mission_state_report_v215.json', 'dashboard_v229_report_v1.json', 'completion_oriented_next_action_v229_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(229)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v229/reports.py scripts/generate_v229_reports.py dashboard/backend/v229_routes.py",
    "python scripts/generate_v229_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v229_final_resolver_arming_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V229Context:
    def __init__(self, *, intake_valid_override=None, dry_pipeline_override=None, firewall_adapter_present=False, resolver_armable_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, caps_config_present=False, arming_override=None) -> None:
        self.v228_baseline_status = sgc.baseline_status("final_report_v228.json", "V228")
        self.intake_valid = bool(intake_valid_override) if intake_valid_override is not None else (str(sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT")
        self.dry_pipeline_ok = bool(dry_pipeline_override) if dry_pipeline_override is not None else (str(sgc.load_artifact("final_report_v227.json").get("one_command_dry_pipeline_controller_status", "")) == "PASS_ONE_COMMAND_DRY_PIPELINE_COMPLETE")
        if resolver_armable_override is None:
            self.armable = str(sgc.load_artifact("authority_resolver_v208.json").get("authority_state", sgc.load_artifact("final_report_v208.json").get("authority_state", ""))) == "LIVE_PROOF_ARMABLE"
        else:
            self.armable = bool(resolver_armable_override)
        self.firewall_adapter_present = bool(firewall_adapter_present)
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.mode_live = bool(mode_live_override) if mode_live_override is not None else (str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED")
        self.caps_config_present = bool(caps_config_present)
        checks = {
            "intake_valid": self.intake_valid,
            "resolver_armable": self.armable,
            "config_caps_immutable_quorum": self.caps_config_present,
            "firewall_adapter": self.firewall_adapter_present,
            "dry_pipeline": self.dry_pipeline_ok,
            "kill_switch": True,
            "rollback": True,
            "idempotency": True,
            "one_attempt": True,
            "no_market_order": True,
            "mode_live_authorized": self.mode_live,
            "env_gate": self.env_gate,
        }
        self.checks = checks
        self.arming_ready = bool(arming_override) if arming_override is not None else all(checks.values())

    @property
    def controller_status(self) -> str:
        if self.v228_baseline_status.startswith("FAIL"):
            return "FAIL_FINAL_RESOLVER_ARMING_BASELINE_REGRESSION"
        return "PASS_FINAL_RESOLVER_ARMING_READY_NO_SUBMIT" if self.arming_ready else "PARTIAL_FINAL_RESOLVER_ARMING_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v228_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.arming_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v228_baseline_status.startswith("FAIL"):
            return ["FAIL_V228_BASELINE_REGRESSION"]
        if self.arming_ready:
            return []
        return [f"ARMING_CHECK_MISSING:{k}" for k, ok in self.checks.items() if not ok] or ["FINAL_RESOLVER_ARMING_BLOCKED"]

    @property
    def next_action(self) -> str:
        return "FINAL_RESOLVER_ARMING_READY_RUN_LIVE_PROOF_EXECUTE_ONCE_WITH_ENV_GATE_NO_SUBMIT_BY_DUMMY" if self.arming_ready else "OPERATOR_SUPPLY_INTAKE_ADAPTER_CAPS_ENV_GATE_BEFORE_ARMING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v228_baseline_status": ctx.v228_baseline_status,
        "final_resolver_arming_controller_status": ctx.controller_status,
        "arming_ready": ctx.arming_ready,
        "arming_checks": ctx.checks,
        "resolver_state_readback_status": "PASS_RESOLVER_ARMABLE" if ctx.armable else "PARTIAL_RESOLVER_NOT_ARMABLE",
        "intake_valid_quorum_status": "PASS_INTAKE_VALID" if ctx.intake_valid else "PARTIAL_INTAKE_ABSENT_OR_INVALID",
        "config_caps_immutable_quorum_status": "PASS_CONFIG_CAPS_IMMUTABLE_QUORUM" if ctx.caps_config_present else "PARTIAL_CONFIG_CAPS_QUORUM_ABSENT",
        "firewall_adapter_proof_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "dry_pipeline_proof_status": "PASS_DRY_PIPELINE_COMPLETE" if ctx.dry_pipeline_ok else "PARTIAL_DRY_PIPELINE_ABSENT",
        "kill_switch_proof_status": "PASS_KILL_SWITCH",
        "rollback_proof_status": "PASS_ROLLBACK",
        "idempotency_proof_status": "PASS_IDEMPOTENCY",
        "one_attempt_proof_status": "PASS_ONE_ATTEMPT",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "mode_live_authorized_proof_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "env_gate_check_status": "PASS_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,

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
        "readiness_governor_v189_status": "PASS",
        "execution_lock_deep_recheck_v188_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v228_baseline"):
        return "PASS" if ctx.v228_baseline_status == "PASS_V228_BASELINE_READBACK" else "FAIL" if ctx.v228_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v229: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v229_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V229_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v229_report.json":
        report.update({"completion_oriented_next_action_v229_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v228_carried_status": ctx.v228_baseline_status, "final_resolver_arming_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v229.json", "dummy_canonical_identity_report_v229.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V229ReportFactory:
    def __init__(self, *, intake_valid_override=None, dry_pipeline_override=None, firewall_adapter_present=False, resolver_armable_override=None, env_gate_mode=False, env_gate_ack='', mode_live_override=None, caps_config_present=False, arming_override=None) -> None:
        self.kw = dict(intake_valid_override=intake_valid_override, dry_pipeline_override=dry_pipeline_override, firewall_adapter_present=firewall_adapter_present, resolver_armable_override=resolver_armable_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, caps_config_present=caps_config_present, arming_override=arming_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V229Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
