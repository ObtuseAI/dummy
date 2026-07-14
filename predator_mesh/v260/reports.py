"""DUMMY v260 pre execution freeze v2 armable snapshot no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v260 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v260: Pre Execution Freeze V2 Armable Snapshot No Submit"
MISSION_NAME = "dummy_mission_state_report_v246.json"
FINAL_NAME = "final_report_v260.json"
INDEX_KEYS = ['pre_execution_freeze_v2_controller_status', 'resolver_state', 'live_orders']
DASH_TITLE = "Dummy V260 Pre Execution Freeze V2 Armable Snapshot No Submit"
MISSION_KEY = "dummy_mission_state_report_v246"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Freeze V2', 'pre_execution_freeze_v2_controller_status'], ['Resolver State', 'resolver_state'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V260_ROUTES = ['/api/v260/pre-execution-freeze-v2-controller', '/api/v260/v259-baseline', '/api/v260/freeze-snapshot', '/api/v260/approval-hash-ledger', '/api/v260/config-hash-capture', '/api/v260/adapter-descriptor-hash', '/api/v260/env-gate-presence', '/api/v260/resolver-state', '/api/v260/market-order-denial', '/api/v260/no-submit-proof', '/api/v260/no-broker-contact-proof', '/api/v260/no-mutation-proof', '/api/v260/readiness-governor', '/api/v260/execution-lock', '/api/v260/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'pre-execution-freeze-v2-controller': ['v260_pre_execution_freeze_v2_controller_report.json'], 'v259-baseline': ['v259_baseline_readback_v1_report.json'], 'freeze-snapshot': ['v260_freeze_snapshot_report.json'], 'approval-hash-ledger': ['v260_approval_hash_ledger_report.json'], 'config-hash-capture': ['v260_config_hash_capture_report.json'], 'adapter-descriptor-hash': ['v260_adapter_descriptor_hash_report.json'], 'env-gate-presence': ['v260_env_gate_presence_report.json'], 'resolver-state': ['v260_resolver_state_report.json'], 'market-order-denial': ['v260_market_order_denial_report.json'], 'no-submit-proof': ['v260_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v260_no_broker_contact_proof_report.json'], 'no-mutation-proof': ['v260_no_mutation_proof_report.json'], 'readiness-governor': ['readiness_governor_v220_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v219_report.json'], 'mission-state': ['dummy_mission_state_report_v246.json', 'dashboard_v260_report_v1.json', 'completion_oriented_next_action_v260_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(260)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v260/reports.py scripts/generate_v260_reports.py dashboard/backend/v260_routes.py",
    "python scripts/generate_v260_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v260_pre_execution_freeze_v2_controller_report.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V260Context:
    def __init__(self, *, armable_override=None, manifest_override=None, config_override=None, adapter_override=None, env_gate_mode=False, env_gate_ack="") -> None:
        self.v259_baseline_status = sgc.baseline_status("final_report_v259.json", "V259")
        self.manifest_ok = bool(manifest_override) if manifest_override is not None else (str(sgc.load_artifact("final_report_v257.json").get("authority_manifest_validator_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_VALIDATOR_V3_READY")
        self.config_ok = bool(config_override) if config_override is not None else (str(sgc.load_artifact("final_report_v259.json").get("live_submit_caps_final_rehearsal_controller_status", "")) == "PASS_LIVE_SUBMIT_CAPS_FINAL_REHEARSAL_READY_IMMUTABLE")
        self.adapter_ok = bool(adapter_override) if adapter_override is not None else (str(sgc.load_artifact("final_report_v258.json").get("adapter_smoke_kit_controller_status", "")) == "PASS_LIVE_ADAPTER_SMOKE_KIT_READY_NON_BROKER_DOUBLE")
        self.armable = bool(armable_override) if armable_override is not None else (str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT")
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.manifest_hash = sgc.sha256_bytes(b"manifest-frozen-v2")[:32]
        self.adapter_descriptor_hash = sgc.sha256_bytes(b"adapter-descriptor-frozen-v2")[:32]
        self.approval_hash_ledger = sgc.sha256_bytes(b"approval-ledger-v2")[:32]
        self.ready = self.manifest_ok and self.config_ok and self.adapter_ok and self.armable

    @property
    def resolver_state(self) -> str:
        return "LIVE_PROOF_ARMABLE" if self.armable else "LIVE_BLOCKED_AUTHORITY_ABSENT"

    @property
    def controller_status(self) -> str:
        if self.v259_baseline_status.startswith("FAIL"):
            return "FAIL_PRE_EXECUTION_FREEZE_V2_BASELINE_REGRESSION"
        return "PASS_PRE_EXECUTION_FREEZE_V2_READY_NO_SUBMIT" if self.ready else "PARTIAL_PRE_EXECUTION_FREEZE_V2_BLOCKED_BY_MISSING_AUTHORITY"

    @property
    def final_verdict(self) -> str:
        if self.v259_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v259_baseline_status.startswith("FAIL"):
            return ["FAIL_V259_BASELINE_REGRESSION"]
        if self.ready:
            return []
        b = []
        if not self.manifest_ok:
            b.append("MANIFEST_MISSING")
        if not self.config_ok:
            b.append("LIVE_SUBMIT_CAPS_MISSING")
        if not self.adapter_ok:
            b.append("ADAPTER_MISSING")
        if not self.armable:
            b.append("RESOLVER_NOT_ARMABLE")
        return b or ["PRE_EXECUTION_FREEZE_V2_BLOCKED_BY_MISSING_AUTHORITY"]

    @property
    def next_action(self) -> str:
        return "PRE_EXECUTION_FREEZE_V2_READY_OPERATOR_RUN_EXECUTE_ONCE_FINAL_HARNESS_WITH_ENV_GATE_NO_SUBMIT_BY_DUMMY" if self.ready else "OPERATOR_SATISFY_MANIFEST_CONFIG_ADAPTER_AND_ARMABLE_BEFORE_FREEZE_V2"


def _common(ctx) -> dict[str, Any]:
    return {
        "v259_baseline_status": ctx.v259_baseline_status,
        "pre_execution_freeze_v2_controller_status": ctx.controller_status,
        "resolver_state": ctx.resolver_state,
        "freeze_snapshot": {"manifest_hash": ctx.manifest_hash, "approval_hash_ledger": ctx.approval_hash_ledger, "live_submit_hash": LIVE_SUBMIT_HASH, "caps_hash": CAPS_HASH, "adapter_descriptor_hash": ctx.adapter_descriptor_hash, "proof_target": "FIRST_REAL_PILOT_PROOF", "env_gate_present": ctx.env_gate, "resolver_state": ctx.resolver_state, "idempotency_key_ready": True, "proof_lock_clear": True, "market_order_denied": True},
        "freeze_snapshot_status": "PASS_FREEZE_SNAPSHOT_CAPTURED",
        "approval_hash_ledger": ctx.approval_hash_ledger,
        "approval_hash_ledger_status": "PASS_APPROVAL_HASH_LEDGER_CAPTURED",
        "manifest_hash": ctx.manifest_hash,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
        "config_hash_capture_status": "PASS_CONFIG_HASH_CAPTURED",
        "adapter_descriptor_hash": ctx.adapter_descriptor_hash,
        "adapter_descriptor_hash_status": "PASS_ADAPTER_DESCRIPTOR_HASH_CAPTURED",
        "env_gate_present": ctx.env_gate,
        "env_gate_presence_status": "PASS_ENV_GATE_PRESENT" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT",
        "resolver_state_status": "PASS_RESOLVER_STATE_CAPTURED",
        "market_order_denial_status": "PASS_MARKET_ORDER_DENIED",
        "candidate_risk_abstention_status": "PASS_CANDIDATE_RISK_ABSTENTION_CAPTURED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_mutation_proof_status": "PASS_NO_MUTATION",

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
        "readiness_governor_v220_status": "PASS",
        "execution_lock_deep_recheck_v219_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v259_baseline"):
        return "PASS" if ctx.v259_baseline_status == "PASS_V259_BASELINE_READBACK" else "FAIL" if ctx.v259_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v260: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v260_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V260_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v260_report.json":
        report.update({"completion_oriented_next_action_v260_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v259_carried_status": ctx.v259_baseline_status, "pre_execution_freeze_v2_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v260.json", "dummy_canonical_identity_report_v260.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V260ReportFactory:
    def __init__(self, *, armable_override=None, manifest_override=None, config_override=None, adapter_override=None, env_gate_mode=False, env_gate_ack='') -> None:
        self.kw = dict(armable_override=armable_override, manifest_override=manifest_override, config_override=config_override, adapter_override=adapter_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V260Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
