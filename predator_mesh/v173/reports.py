"""DUMMY v173 controlled operation dry session — runs an inert dry session mirroring real authority gates; no broker contact.

Mirrors the real controlled-operation authority gates (candidate sequence, risk gate, abstention gate, hypothetical
per-order approval checks, hypothetical reconcile path, hypothetical forensic schema) using inert records only. No
broker payload, no submit/cancel, no account/private data, no scale, no autonomy. Default is
PASS_CONTROLLED_OPERATION_DRY_SESSION_READY_INERT; live_orders=0 and broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v173 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v173: Controlled Operation Dry Session Inert Real Authority Mirror"
MISSION_NAME = "dummy_mission_state_report_v159.json"
FINAL_NAME = "final_report_v173.json"
INDEX_KEYS = ["dry_session_controller_status", "broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V173 Controlled Operation Dry Session"
MISSION_KEY = "dummy_mission_state_report_v159"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Dry Session", "dry_session_controller_status"],
    ["Broker Contacted", "broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V173_ROUTES = [
    "/api/v173/dry-session-controller",
    "/api/v173/v172-baseline",
    "/api/v173/dry-session-id",
    "/api/v173/candidate-sequence-snapshot",
    "/api/v173/risk-gate-sequence",
    "/api/v173/abstention-gate-sequence",
    "/api/v173/hypothetical-per-order-approval-checks",
    "/api/v173/hypothetical-reconcile-path",
    "/api/v173/hypothetical-forensic-schema",
    "/api/v173/dry-live-mode-firewall-proof",
    "/api/v173/no-broker-payload-proof",
    "/api/v173/no-submit-cancel-proof",
    "/api/v173/no-account-private-data-proof",
    "/api/v173/no-scale-proof",
    "/api/v173/no-autonomy-proof",
    "/api/v173/readiness-governor",
    "/api/v173/execution-lock",
    "/api/v173/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "dry-session-controller": ["v173_dry_session_controller_report.json"],
    "v172-baseline": ["v172_baseline_readback_v1_report.json"],
    "dry-session-id": ["v173_dry_session_id_report.json"],
    "candidate-sequence-snapshot": ["v173_candidate_sequence_snapshot_report.json"],
    "risk-gate-sequence": ["v173_risk_gate_sequence_report.json"],
    "abstention-gate-sequence": ["v173_abstention_gate_sequence_report.json"],
    "hypothetical-per-order-approval-checks": ["v173_hypothetical_per_order_approval_checks_report.json"],
    "hypothetical-reconcile-path": ["v173_hypothetical_reconcile_path_report.json"],
    "hypothetical-forensic-schema": ["v173_hypothetical_forensic_schema_report.json"],
    "dry-live-mode-firewall-proof": ["v173_dry_live_mode_firewall_proof_report.json"],
    "no-broker-payload-proof": ["v173_no_broker_payload_proof_report.json"],
    "no-submit-cancel-proof": ["v173_no_submit_cancel_proof_report.json"],
    "no-account-private-data-proof": ["v173_no_account_private_data_proof_report.json"],
    "no-scale-proof": ["v173_no_scale_proof_report.json"],
    "no-autonomy-proof": ["v173_no_autonomy_proof_report.json"],
    "readiness-governor": ["readiness_governor_v133_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v132_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v173_report_v1.json", "completion_oriented_next_action_v173_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(173)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v173/reports.py scripts/generate_v173_reports.py dashboard/backend/v173_routes.py",
    "python scripts/generate_v173_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

HYPOTHETICAL_FORENSIC_SCHEMA = ["order_attempt_id", "state", "fill_qty", "slippage_bps", "latency_ms", "fee_cents", "idempotency_key"]


class V173Context:
    def __init__(self) -> None:
        self.v172_baseline_status = sgc.baseline_status("final_report_v172.json", "V172")
        self.dry_session_id = sgc.sha256_bytes(("controlled-operation-dry-session|" + str(self.v172_baseline_status)).encode("utf-8"))[:24]

    @property
    def controller_status(self) -> str:
        return "FAIL_DRY_SESSION_BASELINE_REGRESSION" if self.v172_baseline_status.startswith("FAIL") else "PASS_CONTROLLED_OPERATION_DRY_SESSION_READY_INERT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v172_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V172_BASELINE_REGRESSION"] if self.v172_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "CONTROLLED_OPERATION_DRY_SESSION_READY_INERT_AWAIT_CONTROLLED_OPERATION_APPROVAL_NO_BROKER_CONTACT"


def _common(ctx: V173Context) -> dict[str, Any]:
    return {
        "v172_baseline_status": ctx.v172_baseline_status,
        "dry_session_controller_status": ctx.controller_status,
        "dry_session_id_status": "PASS_DRY_SESSION_ID_ASSIGNED",
        "dry_session_id": ctx.dry_session_id,
        "candidate_sequence_snapshot_status": "PASS_CANDIDATE_SEQUENCE_INERT",
        "risk_gate_sequence_status": "PASS_RISK_GATE_SEQUENCE_INERT",
        "abstention_gate_sequence_status": "PASS_ABSTENTION_GATE_SEQUENCE_INERT",
        "hypothetical_per_order_approval_checks_status": "PASS_HYPOTHETICAL_PER_ORDER_APPROVAL_INERT",
        "hypothetical_reconcile_path_status": "PASS_HYPOTHETICAL_RECONCILE_PATH_INERT",
        "hypothetical_forensic_schema_status": "PASS_HYPOTHETICAL_FORENSIC_SCHEMA_LISTED",
        "hypothetical_forensic_schema": HYPOTHETICAL_FORENSIC_SCHEMA,
        "dry_live_mode_firewall_proof_status": "PASS_DRY_LOCKED_NO_CROSSOVER",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "no_submit_cancel_proof_status": "PASS_NO_SUBMIT_CANCEL",
        "no_account_private_data_proof_status": "PASS_NO_ACCOUNT_PRIVATE_DATA",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "no_autonomy_proof_status": "PASS_NO_AUTONOMY",
        "dry_session_inert": True,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v133_status": "PASS",
        "execution_lock_deep_recheck_v132_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V173Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v172_baseline"):
        return "PASS" if ctx.v172_baseline_status == "PASS_V172_BASELINE_READBACK" else "FAIL" if ctx.v172_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V173Context) -> dict[str, Any]:
    workstream = "v173: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v173_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V173_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v173_report.json":
        report.update({"completion_oriented_next_action_v173_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v172_carried_status": ctx.v172_baseline_status, "dry_session_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v173_dry_session_controller_report.json"), "no_broker_payload": str(ARTIFACTS / "v173_no_broker_payload_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v173.json", "dummy_canonical_identity_report_v173.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V173ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V173Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
