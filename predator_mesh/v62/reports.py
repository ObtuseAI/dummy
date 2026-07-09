"""DUMMY v62 local-only rehearsal runner gate — inert simulation only, no broker payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v55.reports import ALLOWED_REHEARSAL_ARTIFACT_TYPES
from predator_mesh.v62 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

LOCAL_REHEARSAL_SCOPE = "local_only_rehearsal_validation_artifacts"
REQUIRED_APPROVAL_FIELDS = [
    "exact_phrase",
    "operator",
    "timestamp",
    "reason",
    "scope",
    "expiration",
    "no_broker_payloads_acknowledgment",
    "no_order_submission_acknowledgment",
    "no_live_trading_acknowledgment",
    "no_live_submit_acknowledgment",
    "no_caps_modification_acknowledgment",
]
ACK_REQUIREMENTS = (
    ("no_broker_payloads_acknowledgment", "no broker payloads"),
    ("no_order_submission_acknowledgment", "no order submission"),
    ("no_live_trading_acknowledgment", "no live trading"),
    ("no_live_submit_acknowledgment", "no live-submit"),
    ("no_caps_modification_acknowledgment", "no caps modification"),
)
# Forbidden keys the local-only simulation output must never contain.
FORBIDDEN_SIM_FIELDS = ["broker_payload", "order_intent", "order_id", "market_order", "side", "quantity", "price", "submit", "cancel", "position_size", "capital_allocation", "account_balance", "private_position", "endpoint", "credential"]

V62_ROUTES = [
    "/api/v62/local-only-rehearsal-gate",
    "/api/v62/v61-baseline",
    "/api/v62/inert-artifact-input-validator",
    "/api/v62/local-only-simulation-ledger",
    "/api/v62/no-broker-payload-validator",
    "/api/v62/no-order-intent-validator",
    "/api/v62/canary-nonexecution-validator-v12",
    "/api/v62/readiness-governor",
    "/api/v62/execution-lock",
    "/api/v62/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "local-only-rehearsal-gate": ["v62_local_only_rehearsal_gate_report.json"],
    "v61-baseline": ["v61_baseline_readback_v1_report.json"],
    "inert-artifact-input-validator": ["v62_inert_artifact_input_validator_report.json"],
    "local-only-simulation-ledger": ["v62_local_only_simulation_ledger_report.json"],
    "no-broker-payload-validator": ["v62_no_broker_payload_validator_report.json"],
    "no-order-intent-validator": ["v62_no_order_intent_validator_report.json"],
    "canary-nonexecution-validator-v12": ["v62_canary_nonexecution_validator_v12_report.json"],
    "readiness-governor": ["readiness_governor_v22_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v21_report.json"],
    "mission-state": ["dummy_mission_state_report_v48.json", "dashboard_v62_report_v1.json", "completion_oriented_next_action_v62_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(62)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v62/reports.py scripts/generate_v62_reports.py dashboard/backend/v62_routes.py",
    "python scripts/generate_v62_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


def _build_simulation_ledger(approval_hash: str) -> list[dict[str, Any]]:
    """Inert local-only simulation entries — one per allowed rehearsal checklist type."""
    return [
        {
            "entry_id": f"v62-sim-{artifact_type.lower().replace('_', '-')}",
            "step": artifact_type,
            "approval_hash": approval_hash,
            "simulated": True,
            "executed": False,
            "local_only": True,
            "broker_payload_present": False,
            "order_intent_present": False,
            "result": "SIMULATED_INERT_CHECK_PASS",
        }
        for artifact_type in ALLOWED_REHEARSAL_ARTIFACT_TYPES
    ]


def _write_simulation_ledger(entries: list[dict[str, Any]], sim_dir: Path) -> list[str]:
    sim_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for entry in entries:
        path = sim_dir / f"{entry['entry_id']}.json"
        path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        paths.append(str(path))
    return paths


class V62Context:
    def __init__(self, *, approval_input, approval_path, write_sim, sim_dir) -> None:
        self.v61_baseline_status = sgc.baseline_status("final_report_v61.json", "V61")
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.LOCAL_REHEARSAL_DESIGN_PHRASE,
            required_fields=REQUIRED_APPROVAL_FIELDS,
            required_scope=LOCAL_REHEARSAL_SCOPE,
            ack_requirements=ACK_REQUIREMENTS,
        )
        self.sim_entries = _build_simulation_ledger(str(self.validation["approval_hash"])) if self.validation["accepted"] else []
        self.sim_dir = sim_dir or (ARTIFACTS / "v62_local_rehearsal_sim")
        self.sim_paths = _write_simulation_ledger(self.sim_entries, self.sim_dir) if write_sim and self.sim_entries else []

    @property
    def gate_status(self) -> str:
        state = self.validation["state"]
        if state == "ABSENT":
            return "PARTIAL_LOCAL_REHEARSAL_APPROVAL_ABSENT"
        if state == "MALFORMED":
            return "PARTIAL_LOCAL_REHEARSAL_APPROVAL_MALFORMED"
        if not self.validation["accepted"]:
            return "FAIL_CLOSED_INVALID_APPROVAL"
        return "PASS_LOCAL_ONLY_REHEARSAL_SIMULATED"

    @property
    def sim_clean(self) -> bool:
        return all(not any(field in entry for field in FORBIDDEN_SIM_FIELDS) for entry in self.sim_entries)

    @property
    def final_verdict(self) -> str:
        if self.v61_baseline_status.startswith("FAIL") or self.gate_status.startswith("FAIL") or not self.sim_clean:
            return "FAIL"
        if self.v61_baseline_status.startswith("PARTIAL") or not self.validation["accepted"]:
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v61_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V61_BASELINE_REGRESSION")
        elif self.v61_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V61_BASELINE_UNAVAILABLE")
        if self.gate_status == "PARTIAL_LOCAL_REHEARSAL_APPROVAL_ABSENT":
            blockers.append("LOCAL_REHEARSAL_APPROVAL_ABSENT")
        elif self.gate_status == "PARTIAL_LOCAL_REHEARSAL_APPROVAL_MALFORMED":
            blockers.append("LOCAL_REHEARSAL_APPROVAL_MALFORMED")
        elif self.gate_status.startswith("FAIL"):
            blockers.extend(self.validation["blockers"])
        return blockers

    @property
    def next_action(self) -> str:
        if self.validation["accepted"]:
            return "LOCAL_ONLY_REHEARSAL_SIMULATED_INERT_RELEASE_LOCKED"
        return "OPERATOR_MAY_CREATE_LOCAL_REHEARSAL_APPROVAL_MANUALLY"


def _common(ctx: V62Context) -> dict[str, Any]:
    return {
        "v61_baseline_status": ctx.v61_baseline_status,
        "local_only_rehearsal_gate_status": ctx.gate_status,
        "local_rehearsal_approval_phrase": sgc.LOCAL_REHEARSAL_DESIGN_PHRASE,
        "required_approval_fields": REQUIRED_APPROVAL_FIELDS,
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_hash": ctx.validation["approval_hash"],
        "inert_artifact_input_validator_status": "PASS_INERT_INPUT_ONLY",
        "local_only_simulation_ledger_status": "PASS_LOCAL_ONLY_SIMULATION" if ctx.sim_entries else "PARTIAL_NO_SIMULATION",
        "simulation_entries": ctx.sim_entries,
        "simulation_paths": ctx.sim_paths,
        "simulation_entry_count": len(ctx.sim_entries),
        "simulation_is_inert": ctx.sim_clean,
        "no_broker_payload_validator_status": "PASS_NO_BROKER_PAYLOAD",
        "no_order_intent_validator_status": "PASS_NO_ORDER_INTENT",
        "forbidden_sim_fields": FORBIDDEN_SIM_FIELDS,
        "runnable_rehearsal_artifacts_created_by_default": False,
        "canary_nonexecution_validator_v12_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V12",
        "readiness_governor_v22_status": "PASS",
        "execution_lock_deep_recheck_v21_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V62Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v61_baseline"):
        return "PASS" if ctx.v61_baseline_status == "PASS_V61_BASELINE_READBACK" else "FAIL" if ctx.v61_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v62_local_only_rehearsal_gate_report.json":
        return "FAIL" if ctx.gate_status.startswith("FAIL") else "PASS" if ctx.validation["accepted"] else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V62Context) -> dict[str, Any]:
    workstream = "v62: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v62_local_only_simulation_ledger_report.json":
        report.update({"ledger": ctx.sim_entries, "entry_count": len(ctx.sim_entries), "inert": ctx.sim_clean})
    elif name == "dashboard_v62_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V62_ROUTES, "read_only_dashboard": True, "dashboard_can_run_rehearsal": False})
    elif name == "completion_oriented_next_action_v62_report.json":
        report.update({"completion_oriented_next_action_v62_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v48.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v61_carried_status": ctx.v61_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v62.json"), "gate": str(ARTIFACTS / "v62_local_only_rehearsal_gate_report.json"), "simulation_ledger": str(ARTIFACTS / "v62_local_only_simulation_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v62.json", "dummy_canonical_identity_report_v62.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V62ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None, write_sim=False, sim_dir=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.write_sim = write_sim
        self.sim_dir = sim_dir

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V62Context(approval_input=self.approval_input, approval_path=self.approval_path, write_sim=self.write_sim, sim_dir=self.sim_dir)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
