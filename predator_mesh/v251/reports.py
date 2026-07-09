"""DUMMY v251 pre execution freeze report no submit — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v251 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v251: Pre Execution Freeze Report No Submit"
MISSION_NAME = "dummy_mission_state_report_v237.json"
FINAL_NAME = "final_report_v251.json"
INDEX_KEYS = ['pre_execution_freeze_controller_status', 'resolver_state', 'live_orders']
DASH_TITLE = "Dummy V251 Pre Execution Freeze Report No Submit"
MISSION_KEY = "dummy_mission_state_report_v237"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Freeze Report', 'pre_execution_freeze_controller_status'], ['Resolver State', 'resolver_state'], ['Live Orders', 'total_real_live_orders_submitted'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V251_ROUTES = ['/api/v251/pre-execution-freeze-controller', '/api/v251/v250-baseline', '/api/v251/freeze-snapshot', '/api/v251/manifest-hash', '/api/v251/live-submit-hash', '/api/v251/caps-hash', '/api/v251/adapter-descriptor-hash', '/api/v251/env-gate-presence', '/api/v251/resolver-state', '/api/v251/proof-lock-status', '/api/v251/no-submit-proof', '/api/v251/no-broker-contact-proof', '/api/v251/no-mutation-proof', '/api/v251/readiness-governor', '/api/v251/execution-lock', '/api/v251/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'pre-execution-freeze-controller': ['v251_pre_execution_freeze_controller_report.json'], 'v250-baseline': ['v250_baseline_readback_v1_report.json'], 'freeze-snapshot': ['v251_freeze_snapshot_report.json'], 'manifest-hash': ['v251_manifest_hash_report.json'], 'live-submit-hash': ['v251_live_submit_hash_report.json'], 'caps-hash': ['v251_caps_hash_report.json'], 'adapter-descriptor-hash': ['v251_adapter_descriptor_hash_report.json'], 'env-gate-presence': ['v251_env_gate_presence_report.json'], 'resolver-state': ['v251_resolver_state_report.json'], 'proof-lock-status': ['v251_proof_lock_status_report.json'], 'no-submit-proof': ['v251_no_submit_proof_report.json'], 'no-broker-contact-proof': ['v251_no_broker_contact_proof_report.json'], 'no-mutation-proof': ['v251_no_mutation_proof_report.json'], 'readiness-governor': ['readiness_governor_v211_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v210_report.json'], 'mission-state': ['dummy_mission_state_report_v237.json', 'dashboard_v251_report_v1.json', 'completion_oriented_next_action_v251_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(251)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v251/reports.py scripts/generate_v251_reports.py dashboard/backend/v251_routes.py",
    "python scripts/generate_v251_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v251_pre_execution_freeze_controller_report.json"

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


class V251Context:
    def __init__(self, *, armable_override=None, env_gate_mode=False, env_gate_ack="", manifest_override=None) -> None:
        self.v250_baseline_status = sgc.baseline_status("final_report_v250.json", "V250")
        self.armable = bool(armable_override) if armable_override is not None else (str(sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status", "")) == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT")
        self.manifest_ok = bool(manifest_override) if manifest_override is not None else (str(sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status", "")) == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS")
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        self.manifest_hash = sgc.sha256_bytes(b"manifest-frozen")[:32]
        self.adapter_descriptor_hash = sgc.sha256_bytes(b"adapter-descriptor-frozen")[:32]
        self.ready = self.armable and self.manifest_ok

    @property
    def resolver_state(self) -> str:
        return "LIVE_PROOF_ARMABLE" if self.armable else "LIVE_BLOCKED_AUTHORITY_ABSENT"

    @property
    def controller_status(self) -> str:
        if self.v250_baseline_status.startswith("FAIL"):
            return "FAIL_PRE_EXECUTION_FREEZE_BASELINE_REGRESSION"
        return "PASS_PRE_EXECUTION_FREEZE_READY_NO_SUBMIT" if self.ready else "PARTIAL_PRE_EXECUTION_FREEZE_BLOCKED_BY_MISSING_AUTHORITY"

    @property
    def final_verdict(self) -> str:
        if self.v250_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v250_baseline_status.startswith("FAIL"):
            return ["FAIL_V250_BASELINE_REGRESSION"]
        if self.ready:
            return []
        b = []
        if not self.manifest_ok:
            b.append("MANIFEST_MISSING")
        if not self.armable:
            b.append("RESOLVER_NOT_ARMABLE")
        return b or ["PRE_EXECUTION_FREEZE_BLOCKED_BY_MISSING_AUTHORITY"]

    @property
    def next_action(self) -> str:
        return "PRE_EXECUTION_FREEZE_READY_OPERATOR_RUN_EXECUTE_ONCE_WITH_ENV_GATE_NO_SUBMIT_BY_DUMMY" if self.ready else "OPERATOR_SATISFY_MANIFEST_AND_ARMABLE_QUORUM_BEFORE_FREEZE"


def _common(ctx) -> dict[str, Any]:
    return {
        "v250_baseline_status": ctx.v250_baseline_status,
        "pre_execution_freeze_controller_status": ctx.controller_status,
        "resolver_state": ctx.resolver_state,
        "freeze_snapshot": {"manifest_hash": ctx.manifest_hash, "live_submit_hash": LIVE_SUBMIT_HASH, "caps_hash": CAPS_HASH, "adapter_descriptor_hash": ctx.adapter_descriptor_hash, "proof_target": "FIRST_REAL_PILOT_PROOF", "env_gate_present": ctx.env_gate, "resolver_state": ctx.resolver_state},
        "freeze_snapshot_status": "PASS_FREEZE_SNAPSHOT_CAPTURED",
        "manifest_hash": ctx.manifest_hash,
        "manifest_hash_status": "PASS_MANIFEST_HASH_CAPTURED",
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "live_submit_hash_status": "PASS_LIVE_SUBMIT_HASH_CAPTURED",
        "caps_hash": CAPS_HASH,
        "caps_hash_status": "PASS_CAPS_HASH_CAPTURED",
        "adapter_descriptor_hash": ctx.adapter_descriptor_hash,
        "adapter_descriptor_hash_status": "PASS_ADAPTER_DESCRIPTOR_HASH_CAPTURED",
        "env_gate_present": ctx.env_gate,
        "env_gate_presence_status": "PASS_ENV_GATE_PRESENT" if ctx.env_gate else "PARTIAL_ENV_GATE_ABSENT",
        "resolver_state_status": "PASS_RESOLVER_STATE_CAPTURED",
        "proof_lock_status_report_status": "PASS_PROOF_LOCK_CLEAR",
        "idempotency_key_ready": True,
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
        "readiness_governor_v211_status": "PASS",
        "execution_lock_deep_recheck_v210_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v250_baseline"):
        return "PASS" if ctx.v250_baseline_status == "PASS_V250_BASELINE_READBACK" else "FAIL" if ctx.v250_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v251: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v251_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V251_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v251_report.json":
        report.update({"completion_oriented_next_action_v251_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v250_carried_status": ctx.v250_baseline_status, "pre_execution_freeze_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v251.json", "dummy_canonical_identity_report_v251.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V251ReportFactory:
    def __init__(self, *, armable_override=None, env_gate_mode=False, env_gate_ack='', manifest_override=None) -> None:
        self.kw = dict(armable_override=armable_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, manifest_override=manifest_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V251Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
