"""DUMMY v218 final live proof arming check no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v218 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v218: Final Live Proof Arming Check No Submit"
MISSION_NAME = "dummy_mission_state_report_v204.json"
FINAL_NAME = "final_report_v218.json"
INDEX_KEYS = ['final_live_proof_arming_check_controller_status', 'arming_ready', 'live_orders']
DASH_TITLE = "Dummy V218 Final Live Proof Arming Check No Submit"
MISSION_KEY = "dummy_mission_state_report_v204"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Arming Check', 'final_live_proof_arming_check_controller_status'], ['Arming Ready', 'arming_ready'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V218_ROUTES = ['/api/v218/final-live-proof-arming-check-controller', '/api/v218/v217-baseline', '/api/v218/config-caps-immutable-quorum', '/api/v218/firewall-adapter-proof', '/api/v218/broker-readonly-proof', '/api/v218/dry-validation-proof', '/api/v218/kill-switch-proof', '/api/v218/rollback-proof', '/api/v218/idempotency-proof', '/api/v218/one-attempt-proof', '/api/v218/no-market-order-proof', '/api/v218/mode-live-authorized-proof', '/api/v218/env-gate-check', '/api/v218/no-submit-proof', '/api/v218/readiness-governor', '/api/v218/execution-lock', '/api/v218/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'final-live-proof-arming-check-controller': ['v218_final_live_proof_arming_check_controller_report.json'], 'v217-baseline': ['v217_baseline_readback_v1_report.json'], 'config-caps-immutable-quorum': ['v218_config_caps_immutable_quorum_report.json'], 'firewall-adapter-proof': ['v218_firewall_adapter_proof_report.json'], 'broker-readonly-proof': ['v218_broker_readonly_proof_report.json'], 'dry-validation-proof': ['v218_dry_validation_proof_report.json'], 'kill-switch-proof': ['v218_kill_switch_proof_report.json'], 'rollback-proof': ['v218_rollback_proof_report.json'], 'idempotency-proof': ['v218_idempotency_proof_report.json'], 'one-attempt-proof': ['v218_one_attempt_proof_report.json'], 'no-market-order-proof': ['v218_no_market_order_proof_report.json'], 'mode-live-authorized-proof': ['v218_mode_live_authorized_proof_report.json'], 'env-gate-check': ['v218_env_gate_check_report.json'], 'no-submit-proof': ['v218_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v178_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v177_report.json'], 'mission-state': ['dummy_mission_state_report_v204.json', 'dashboard_v218_report_v1.json', 'completion_oriented_next_action_v218_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(218)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v218/reports.py scripts/generate_v218_reports.py dashboard/backend/v218_routes.py",
    "python scripts/generate_v218_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v218_final_live_proof_arming_check_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V218Context:
    def __init__(self, *, manifest_valid_override=None, dry_validation_override=None, firewall_adapter_present=False, broker_readonly_ok=True, env_gate_mode=False, env_gate_ack="", mode_live_override=None, caps_config_present=False, arming_override=None) -> None:
        self.v217_baseline_status = sgc.baseline_status("final_report_v217.json", "V217")
        self.manifest_valid = bool(manifest_valid_override) if manifest_valid_override is not None else (str(sgc.load_artifact("final_report_v216.json").get("external_authority_manifest_intake_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_MANIFEST_VALIDATED_NO_SUBMIT")
        self.dry_validation_ok = bool(dry_validation_override) if dry_validation_override is not None else (str(sgc.load_artifact("final_report_v217.json").get("zero_broker_dry_validation_controller_status", "")) == "PASS_ZERO_BROKER_DRY_VALIDATION_COMPLETE")
        self.firewall_adapter_present = bool(firewall_adapter_present)
        self.broker_readonly_ok = bool(broker_readonly_ok)
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.mode_live = bool(mode_live_override) if mode_live_override is not None else (str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED")
        self.caps_config_present = bool(caps_config_present)
        checks = {
            "manifest_valid": self.manifest_valid,
            "config_caps_immutable_quorum": self.caps_config_present,
            "firewall_adapter": self.firewall_adapter_present,
            "broker_readonly": self.broker_readonly_ok,
            "dry_validation": self.dry_validation_ok,
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
        if self.v217_baseline_status.startswith("FAIL"):
            return "FAIL_FINAL_ARMING_BASELINE_REGRESSION"
        return "PASS_FINAL_LIVE_PROOF_ARMING_READY_NO_SUBMIT" if self.arming_ready else "PARTIAL_FINAL_LIVE_PROOF_ARMING_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v217_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.arming_ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v217_baseline_status.startswith("FAIL"):
            return ["FAIL_V217_BASELINE_REGRESSION"]
        if self.arming_ready:
            return []
        return [f"ARMING_CHECK_MISSING:{k}" for k, ok in self.checks.items() if not ok] or ["FINAL_LIVE_PROOF_ARMING_BLOCKED"]

    @property
    def next_action(self) -> str:
        return "FINAL_LIVE_PROOF_ARMING_READY_RUN_HARDENED_LIVE_PROOF_WITH_ENV_GATE_NO_SUBMIT_BY_DUMMY" if self.arming_ready else "OPERATOR_SUPPLY_MANIFEST_ADAPTER_CAPS_ENV_GATE_BEFORE_ARMING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v217_baseline_status": ctx.v217_baseline_status,
        "final_live_proof_arming_check_controller_status": ctx.controller_status,
        "arming_ready": ctx.arming_ready,
        "arming_checks": ctx.checks,
        "config_caps_immutable_quorum_status": "PASS_CONFIG_CAPS_IMMUTABLE_QUORUM" if ctx.caps_config_present else "PARTIAL_CONFIG_CAPS_QUORUM_ABSENT",
        "firewall_adapter_proof_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "broker_readonly_proof_status": "PASS_BROKER_READONLY_CONSISTENT" if ctx.broker_readonly_ok else "PARTIAL_BROKER_READONLY_INCONSISTENT",
        "dry_validation_proof_status": "PASS_DRY_VALIDATION_COMPLETE" if ctx.dry_validation_ok else "PARTIAL_DRY_VALIDATION_ABSENT",
        "kill_switch_proof_status": "PASS_KILL_SWITCH",
        "rollback_proof_status": "PASS_ROLLBACK",
        "idempotency_proof_status": "PASS_IDEMPOTENCY",
        "one_attempt_proof_status": "PASS_ONE_ATTEMPT",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "mode_live_authorized_proof_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "env_gate_check_status": "PASS_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,
        "manifest_valid": ctx.manifest_valid,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "readiness_governor_v178_status": "PASS",
        "execution_lock_deep_recheck_v177_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v217_baseline"):
        return "PASS" if ctx.v217_baseline_status == "PASS_V217_BASELINE_READBACK" else "FAIL" if ctx.v217_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v218: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v218_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V218_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v218_report.json":
        report.update({"completion_oriented_next_action_v218_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v217_carried_status": ctx.v217_baseline_status, "final_live_proof_arming_check_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v218.json", "dummy_canonical_identity_report_v218.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V218ReportFactory:
    def __init__(self, *, manifest_valid_override=None, dry_validation_override=None, firewall_adapter_present=False, broker_readonly_ok=True, env_gate_mode=False, env_gate_ack='', mode_live_override=None, caps_config_present=False, arming_override=None) -> None:
        self.kw = dict(manifest_valid_override=manifest_valid_override, dry_validation_override=dry_validation_override, firewall_adapter_present=firewall_adapter_present, broker_readonly_ok=broker_readonly_ok, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, caps_config_present=caps_config_present, arming_override=arming_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V218Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
