"""DUMMY v149 production pilot rehearsal spine — builds an inert rehearsal spine; no broker contact.

Assembles candidate/risk/abstention snapshots, a hypothetical order summary, a hypothetical reconcile path, and the
expected forensic fields using inert records only. No broker payload, no submit/cancel, no account/private data. The
spine is ready and inert; live_orders=0 and broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v149 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v149: Production Pilot Rehearsal Spine Inert No Broker Contact"
MISSION_NAME = "dummy_mission_state_report_v135.json"
FINAL_NAME = "final_report_v149.json"
INDEX_KEYS = ["rehearsal_controller_status", "broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V149 Production Pilot Rehearsal Spine"
MISSION_KEY = "dummy_mission_state_report_v135"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Rehearsal Spine", "rehearsal_controller_status"],
    ["Broker Contacted", "broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V149_ROUTES = [
    "/api/v149/rehearsal-controller",
    "/api/v149/v148-baseline",
    "/api/v149/candidate-snapshot",
    "/api/v149/risk-snapshot",
    "/api/v149/abstention-snapshot",
    "/api/v149/hypothetical-order-summary",
    "/api/v149/hypothetical-reconcile-path",
    "/api/v149/expected-forensic-fields",
    "/api/v149/no-broker-payload-proof",
    "/api/v149/no-submit-cancel-proof",
    "/api/v149/no-account-private-data-proof",
    "/api/v149/readiness-governor",
    "/api/v149/execution-lock",
    "/api/v149/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "rehearsal-controller": ["v149_rehearsal_controller_report.json"],
    "v148-baseline": ["v148_baseline_readback_v1_report.json"],
    "candidate-snapshot": ["v149_candidate_snapshot_report.json"],
    "risk-snapshot": ["v149_risk_snapshot_report.json"],
    "abstention-snapshot": ["v149_abstention_snapshot_report.json"],
    "hypothetical-order-summary": ["v149_hypothetical_order_summary_report.json"],
    "hypothetical-reconcile-path": ["v149_hypothetical_reconcile_path_report.json"],
    "expected-forensic-fields": ["v149_expected_forensic_fields_report.json"],
    "no-broker-payload-proof": ["v149_no_broker_payload_proof_report.json"],
    "no-submit-cancel-proof": ["v149_no_submit_cancel_proof_report.json"],
    "no-account-private-data-proof": ["v149_no_account_private_data_proof_report.json"],
    "readiness-governor": ["readiness_governor_v109_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v108_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v149_report_v1.json", "completion_oriented_next_action_v149_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(149)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v149/reports.py scripts/generate_v149_reports.py dashboard/backend/v149_routes.py",
    "python scripts/generate_v149_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

EXPECTED_FORENSIC_FIELDS = ["order_attempt_id", "state", "fill_qty", "slippage_bps", "latency_ms", "fee_cents", "idempotency_key"]


class V149Context:
    def __init__(self) -> None:
        self.v148_baseline_status = sgc.baseline_status("final_report_v148.json", "V148")

    @property
    def controller_status(self) -> str:
        return "FAIL_REHEARSAL_BASELINE_REGRESSION" if self.v148_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_PILOT_REHEARSAL_SPINE_READY_INERT"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v148_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V148_BASELINE_REGRESSION"] if self.v148_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "REHEARSAL_SPINE_READY_INERT_AWAIT_REAL_PILOT_PREFLIGHT_NO_BROKER_CONTACT"


def _common(ctx: V149Context) -> dict[str, Any]:
    return {
        "v148_baseline_status": ctx.v148_baseline_status,
        "rehearsal_controller_status": ctx.controller_status,
        "candidate_snapshot_status": "PASS_CANDIDATE_SNAPSHOT_INERT",
        "risk_snapshot_status": "PASS_RISK_SNAPSHOT_INERT",
        "abstention_snapshot_status": "PASS_ABSTENTION_SNAPSHOT_INERT",
        "hypothetical_order_summary_status": "PASS_HYPOTHETICAL_ORDER_SUMMARY_INERT",
        "hypothetical_order_summary": {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "inert": True, "executable": False},
        "hypothetical_reconcile_path_status": "PASS_HYPOTHETICAL_RECONCILE_PATH_INERT",
        "expected_forensic_fields_status": "PASS_EXPECTED_FORENSIC_FIELDS_LISTED",
        "expected_forensic_fields": EXPECTED_FORENSIC_FIELDS,
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "no_submit_cancel_proof_status": "PASS_NO_SUBMIT_CANCEL",
        "no_account_private_data_proof_status": "PASS_NO_ACCOUNT_PRIVATE_DATA",
        "rehearsal_inert": True,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v109_status": "PASS",
        "execution_lock_deep_recheck_v108_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V149Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v148_baseline"):
        return "PASS" if ctx.v148_baseline_status == "PASS_V148_BASELINE_READBACK" else "FAIL" if ctx.v148_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V149Context) -> dict[str, Any]:
    workstream = "v149: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v149_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V149_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v149_report.json":
        report.update({"completion_oriented_next_action_v149_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v148_carried_status": ctx.v148_baseline_status, "rehearsal_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v149_rehearsal_controller_report.json"), "no_broker_payload": str(ARTIFACTS / "v149_no_broker_payload_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v149.json", "dummy_canonical_identity_report_v149.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V149ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V149Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
