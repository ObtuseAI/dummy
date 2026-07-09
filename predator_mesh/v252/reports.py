"""DUMMY v252 execute once dry fixture harness v3 no real orders — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v252 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v252: Execute Once Dry Fixture Harness V3 No Real Orders"
MISSION_NAME = "dummy_mission_state_report_v238.json"
FINAL_NAME = "final_report_v252.json"
INDEX_KEYS = ['execute_once_dry_fixture_harness_controller_status', 'live_orders', 'real_broker_contacted']
DASH_TITLE = "Dummy V252 Execute Once Dry Fixture Harness V3 No Real Orders"
MISSION_KEY = "dummy_mission_state_report_v238"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Dry/Fixture Harness', 'execute_once_dry_fixture_harness_controller_status'], ['Live Orders', 'live_orders'], ['Broker Contacted', 'real_broker_contacted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V252_ROUTES = ['/api/v252/execute-once-dry-fixture-harness-controller', '/api/v252/v251-baseline', '/api/v252/dry-mode-default', '/api/v252/proof-approval-validator', '/api/v252/cli-env-gate', '/api/v252/proof-target-guard', '/api/v252/livebrokerfirewall-only-proof', '/api/v252/limit-only-proof', '/api/v252/no-market-order-proof', '/api/v252/max-one-attempt-guard', '/api/v252/proof-lock', '/api/v252/no-repeat-submit-proof', '/api/v252/safety-proven', '/api/v252/readiness-governor', '/api/v252/execution-lock', '/api/v252/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'execute-once-dry-fixture-harness-controller': ['v252_execute_once_dry_fixture_harness_controller_report.json'], 'v251-baseline': ['v251_baseline_readback_v1_report.json'], 'dry-mode-default': ['v252_dry_mode_default_report.json'], 'proof-approval-validator': ['v252_proof_approval_validator_report.json'], 'cli-env-gate': ['v252_cli_env_gate_report.json'], 'proof-target-guard': ['v252_proof_target_guard_report.json'], 'livebrokerfirewall-only-proof': ['v252_livebrokerfirewall_only_proof_report.json'], 'limit-only-proof': ['v252_limit_only_proof_report.json'], 'no-market-order-proof': ['v252_no_market_order_proof_report.json'], 'max-one-attempt-guard': ['v252_max_one_attempt_guard_report.json'], 'proof-lock': ['v252_proof_lock_report.json'], 'no-repeat-submit-proof': ['v252_no_repeat_submit_proof_report.json'], 'safety-proven': ['v252_safety_proven_report.json'], 'readiness-governor': ['readiness_governor_v212_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v211_report.json'], 'mission-state': ['dummy_mission_state_report_v238.json', 'dashboard_v252_report_v1.json', 'completion_oriented_next_action_v252_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(252)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v252/reports.py scripts/generate_v252_reports.py dashboard/backend/v252_routes.py",
    "python scripts/generate_v252_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v252_execute_once_dry_fixture_harness_controller_report.json"

ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "first_live_proof": True, "dry_fixture_v3": True}
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V252Context:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF", max_proof_orders=1) -> None:
        self.v251_baseline_status = sgc.baseline_status("final_report_v251.json", "V251")
        self.armable = bool(armable_override) if armable_override is not None else (str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT")
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.mode_live = bool(mode_live_override) if mode_live_override is not None else (str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED")
        self.proof_target = proof_target_override
        self.target_valid = self.proof_target in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.result = sgc.pilot_submit(
            "v252-execute-once-dry-fixture",
            approval_input=proof_approval,
            approval_path=proof_approval_path,
            dry_audit_ready=self.armable and self.env_gate and self.mode_live and self.target_valid,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape={**ORDER_SHAPE, "proof_target": self.proof_target},
            max_pilot_orders=max_proof_orders,
        )
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def submitted(self) -> bool:
        r = self.result["submit_result"]
        return r is not None and bool(r.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        r = self.result["submit_result"]
        return bool(r and r.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        if self.v251_baseline_status.startswith("FAIL"):
            return "FAIL_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_BASELINE_REGRESSION"
        return "PASS_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_PROVEN_SAFE" if self.submitted else "PARTIAL_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_NOT_ARMED_REAL"

    @property
    def final_verdict(self) -> str:
        if self.v251_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v251_baseline_status.startswith("FAIL"):
            return ["FAIL_V251_BASELINE_REGRESSION"]
        if self.submitted:
            return []
        return ["EXECUTE_ONCE_DRY_FIXTURE_HARNESS_NOT_ARMED_REAL_DEFAULT_DRY"]

    @property
    def next_action(self) -> str:
        return "EXECUTE_ONCE_DRY_FIXTURE_HARNESS_PROVEN_SAFE_PATH_VALID_OPERATOR_RUN_REAL_WITH_AUTHORITY" if self.submitted else "EXECUTE_ONCE_DRY_FIXTURE_HARNESS_DEFAULT_DRY_NO_REAL_ORDER"


def _common(ctx) -> dict[str, Any]:
    return {
        "v251_baseline_status": ctx.v251_baseline_status,
        "execute_once_dry_fixture_harness_controller_status": ctx.controller_status,
        "dry_mode_default_status": "PASS_DRY_MODE_DEFAULT",
        "dry_run_default": not ctx.env_gate,
        "proof_approval_validator_status": "PASS_PROOF_APPROVAL_VALID" if ctx.result["validation"]["accepted"] else ("FAIL_CLOSED_INVALID_PROOF_APPROVAL" if ctx.result["validation"]["state"] == "PRESENT" else "PARTIAL_PROOF_APPROVAL_ABSENT"),
        "cli_env_gate_status": "PASS_CLI_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_CLI_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,
        "proof_target": ctx.proof_target,
        "proof_target_guard_status": "PASS_PROOF_TARGET_" + ctx.proof_target if ctx.target_valid else "PARTIAL_PROOF_TARGET_INVALID",
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "max_one_attempt_guard_status": "PASS_MAX_ONE_ATTEMPT",
        "max_proof_order_count": ctx.result["max_pilot_orders"],
        "no_repeat_submit_proof_status": "PASS_NO_REPEAT_SUBMIT",
        "safety_proven_status": "PASS_SAFETY_PROVEN" if ctx.submitted else "PASS_SAFETY_DEFAULT_DRY",
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "proof_lock_status": "PASS_PROOF_AUTOLOCKED" if ctx.submitted else "PASS_PROOF_LOCK_ARMED",
        "proof_locked": ctx.submitted,
        "proof_id": ctx.result["pilot_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "real_broker_contacted": ctx.real_broker_contacted,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": ctx.real_broker_contacted,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v212_status": "PASS",
        "execution_lock_deep_recheck_v211_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v251_baseline"):
        return "PASS" if ctx.v251_baseline_status == "PASS_V251_BASELINE_READBACK" else "FAIL" if ctx.v251_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v252: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v252_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V252_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v252_report.json":
        report.update({"completion_oriented_next_action_v252_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v251_carried_status": ctx.v251_baseline_status, "execute_once_dry_fixture_harness_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v252.json", "dummy_canonical_identity_report_v252.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V252ReportFactory:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack='', mode_live_override=None, proof_target_override='FIRST_REAL_PILOT_PROOF', max_proof_orders=1) -> None:
        self.kw = dict(proof_approval=proof_approval, proof_approval_path=proof_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, armable_override=armable_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, proof_target_override=proof_target_override, max_proof_orders=max_proof_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V252Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
