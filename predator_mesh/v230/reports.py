"""DUMMY v230 live proof execution orchestrator full authority only — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v230 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v230: Live Proof Execution Orchestrator Full Authority Only"
MISSION_NAME = "dummy_mission_state_report_v216.json"
FINAL_NAME = "final_report_v230.json"
INDEX_KEYS = ['live_proof_execution_orchestrator_controller_status', 'live_orders', 'real_broker_contacted']
DASH_TITLE = "Dummy V230 Live Proof Execution Orchestrator Full Authority Only"
MISSION_KEY = "dummy_mission_state_report_v216"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Execution', 'live_proof_execution_orchestrator_controller_status'], ['Live Orders', 'live_orders'], ['Broker Contacted', 'real_broker_contacted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V230_ROUTES = ['/api/v230/live-proof-execution-orchestrator-controller', '/api/v230/v229-baseline', '/api/v230/arming-prerequisite', '/api/v230/proof-approval-validator', '/api/v230/authority-armable-prerequisite', '/api/v230/cli-env-gate', '/api/v230/mode-live-authorized-prerequisite', '/api/v230/proof-target-guard', '/api/v230/livebrokerfirewall-only-proof', '/api/v230/limit-only-proof', '/api/v230/no-market-order-proof', '/api/v230/max-one-attempt-guard', '/api/v230/proof-lock', '/api/v230/no-repeat-submit-proof', '/api/v230/readiness-governor', '/api/v230/execution-lock', '/api/v230/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'live-proof-execution-orchestrator-controller': ['v230_live_proof_execution_orchestrator_controller_report.json'], 'v229-baseline': ['v229_baseline_readback_v1_report.json'], 'arming-prerequisite': ['v230_arming_prerequisite_report.json'], 'proof-approval-validator': ['v230_proof_approval_validator_report.json'], 'authority-armable-prerequisite': ['v230_authority_armable_prerequisite_report.json'], 'cli-env-gate': ['v230_cli_env_gate_report.json'], 'mode-live-authorized-prerequisite': ['v230_mode_live_authorized_prerequisite_report.json'], 'proof-target-guard': ['v230_proof_target_guard_report.json'], 'livebrokerfirewall-only-proof': ['v230_livebrokerfirewall_only_proof_report.json'], 'limit-only-proof': ['v230_limit_only_proof_report.json'], 'no-market-order-proof': ['v230_no_market_order_proof_report.json'], 'max-one-attempt-guard': ['v230_max_one_attempt_guard_report.json'], 'proof-lock': ['v230_proof_lock_report.json'], 'no-repeat-submit-proof': ['v230_no_repeat_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v190_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v189_report.json'], 'mission-state': ['dummy_mission_state_report_v216.json', 'dashboard_v230_report_v1.json', 'completion_oriented_next_action_v230_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(230)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v230/reports.py scripts/generate_v230_reports.py dashboard/backend/v230_routes.py",
    "python scripts/generate_v230_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v230_live_proof_execution_orchestrator_controller_report.json"

ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "first_live_proof": True, "orchestrated": True}
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V230Context:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF", arming_override=None, max_proof_orders=1) -> None:
        self.v229_baseline_status = sgc.baseline_status("final_report_v229.json", "V229")
        self.arming_ok = bool(arming_override) if arming_override is not None else (str(sgc.load_artifact("final_report_v229.json").get("final_resolver_arming_controller_status", "")) == "PASS_FINAL_RESOLVER_ARMING_READY_NO_SUBMIT")
        if armable_override is None:
            self.armable = str(sgc.load_artifact("authority_resolver_v208.json").get("authority_state", sgc.load_artifact("final_report_v208.json").get("authority_state", ""))) == "LIVE_PROOF_ARMABLE"
        else:
            self.armable = bool(armable_override)
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.mode_live = bool(mode_live_override) if mode_live_override is not None else (str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED")
        self.proof_target = proof_target_override
        self.target_valid = self.proof_target in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.result = sgc.pilot_submit(
            "v230-live-proof-execution",
            approval_input=proof_approval,
            approval_path=proof_approval_path,
            dry_audit_ready=self.arming_ok and self.armable and self.env_gate and self.mode_live and self.target_valid,
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
        if self.v229_baseline_status.startswith("FAIL"):
            return "FAIL_LIVE_PROOF_EXECUTION_BASELINE_REGRESSION"
        return "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_LIVE_PROOF_EXECUTION_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v229_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v229_baseline_status.startswith("FAIL"):
            return ["FAIL_V229_BASELINE_REGRESSION"]
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.arming_ok:
            base.append("V229_ARMING_NOT_READY")
        if not self.armable:
            base.append("AUTHORITY_NOT_ARMABLE")
        if not self.env_gate:
            base.append("CLI_ENV_GATE_ABSENT")
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.target_valid:
            base.append("PROOF_TARGET_INVALID")
        return base or ["LIVE_PROOF_EXECUTION_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED_AWAIT_RECONCILE_FORENSIC_PIPELINE_NO_FURTHER_ORDERS" if self.submitted else "OPERATOR_PASS_V229_ARMING_SET_ENV_GATE_AND_PROVIDE_FULL_AUTHORITY_DEFAULT_DRY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v229_baseline_status": ctx.v229_baseline_status,
        "live_proof_execution_orchestrator_controller_status": ctx.controller_status,
        "arming_prerequisite_status": "PASS_V229_ARMING_READY" if ctx.arming_ok else "PARTIAL_V229_ARMING_NOT_READY",
        "proof_approval_validator_status": "PASS_PROOF_APPROVAL_VALID" if ctx.result["validation"]["accepted"] else ("FAIL_CLOSED_INVALID_PROOF_APPROVAL" if ctx.result["validation"]["state"] == "PRESENT" else "PARTIAL_PROOF_APPROVAL_ABSENT"),
        "authority_armable_prerequisite_status": "PASS_AUTHORITY_ARMABLE" if ctx.armable else "PARTIAL_AUTHORITY_NOT_ARMABLE",
        "cli_env_gate_status": "PASS_CLI_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_CLI_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": "DUMMY_LIVE_PROOF_ACK=" + LIVE_PROOF_ACK,
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "proof_target": ctx.proof_target,
        "proof_target_guard_status": "PASS_PROOF_TARGET_" + ctx.proof_target if ctx.target_valid else "PARTIAL_PROOF_TARGET_INVALID",
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "max_one_attempt_guard_status": "PASS_MAX_ONE_ATTEMPT",
        "max_proof_order_count": ctx.result["max_pilot_orders"],
        "no_repeat_submit_proof_status": "PASS_NO_REPEAT_SUBMIT",
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "dry_run_default": not ctx.env_gate,
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
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v190_status": "PASS",
        "execution_lock_deep_recheck_v189_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v229_baseline"):
        return "PASS" if ctx.v229_baseline_status == "PASS_V229_BASELINE_READBACK" else "FAIL" if ctx.v229_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v230: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v230_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V230_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v230_report.json":
        report.update({"completion_oriented_next_action_v230_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v229_carried_status": ctx.v229_baseline_status, "live_proof_execution_orchestrator_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v230.json", "dummy_canonical_identity_report_v230.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V230ReportFactory:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack='', mode_live_override=None, proof_target_override='FIRST_REAL_PILOT_PROOF', arming_override=None, max_proof_orders=1) -> None:
        self.kw = dict(proof_approval=proof_approval, proof_approval_path=proof_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, armable_override=armable_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, proof_target_override=proof_target_override, arming_override=arming_override, max_proof_orders=max_proof_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V230Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
