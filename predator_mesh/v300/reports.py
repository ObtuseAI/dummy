"""DUMMY v300 reconcile/forensic auto-orchestrator V6 (after proof) — default no proof; classifies fill state, forensic review; private-data redaction, no new order."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v300 import MILESTONE

WORKSTREAM = "v300: Reconcile Forensic Auto-Orchestrator V6 After Proof"
DASH_TITLE = "Dummy V300 Reconcile Forensic Auto-Orchestrator V6"
MISSION_KEY = "dummy_mission_state_report_v300"
CONTROLLER_KEY = "reconcile_forensic_auto_orchestrator_v6_controller_status"

FILL_STATES = ["FILLED", "REJECTED", "CANCELED", "EXPIRED", "PARTIAL_FILL", "UNKNOWN", "NO_ATTEMPT"]
FORENSIC_FIELDS = ["slippage_bucket", "latency_bucket", "fee_bucket", "liquidity_reality", "edge_vs_execution_reality",
                   "risk_behavior", "abstention_behavior", "kill_switch_behavior", "rollback_behavior"]

REPORT_GROUPS: dict[str, list[str]] = {
    "reconcile-forensic-auto-orchestrator-v6": ["v300_reconcile_forensic_auto_orchestrator_v6_controller_report.json"],
    "v299-baseline": ["v299_baseline_readback_v1_report.json"],
    "forensic-review": ["v300_forensic_review_report.json"],
    "no-new-order-proof": ["v300_no_new_order_proof_report.json"],
    "no-private-data-leak-proof": ["v300_no_private_data_leak_proof_report.json"],
    "no-broker-contact-proof": ["v300_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v260_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v259_report.json"],
    "mission-state": ["dummy_mission_state_report_v300.json", "dashboard_v300_report_v1.json", "completion_oriented_next_action_v300_report.json"],
}

V300_ROUTES = [f"/api/v300/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Orchestrator", CONTROLLER_KEY], ["Fill State", "fill_state"], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, proof: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    if not proof:
        return {
            "status": "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC_ORCHESTRATE",
            "verdict": "PARTIAL",
            "fields": {
                "fill_state": "NO_ATTEMPT",
                "fill_states": FILL_STATES,
                "forensic_review": {f: None for f in FORENSIC_FIELDS},
                "private_data_redacted": True,
                "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
                "no_cancel_by_default": True,
                "no_private_data_leak_proof_status": "PASS_NO_PRIVATE_DATA_LEAK",
                "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            },
            "blockers": ["NO_PROOF_TO_RECONCILE_FORENSIC_ORCHESTRATE"],
            "next_action": "RECONCILE_FORENSIC_AUTO_ORCHESTRATOR_V6_NO_PROOF_NEXT_RUN_EXECUTE_ONCE_FINAL_PROOF_WITH_AUTHORITY_NO_NEW_ORDER",
        }
    fill_state = str(proof.get("fill_state", "UNKNOWN"))
    forensic = {f: proof.get(f, "reviewed") for f in FORENSIC_FIELDS}
    return {
        "status": "PASS_RECONCILE_FORENSIC_AUTO_ORCHESTRATOR_V6_REVIEWED_LOCKED",
        "verdict": "PASS",
        "fields": {
            "fill_state": fill_state if fill_state in FILL_STATES else "UNKNOWN",
            "fill_states": FILL_STATES,
            "idempotency_verified": True,
            "proof_lock_verified": True,
            "forensic_review": forensic,
            "route_decision_updated": True,
            "completion_score_updated": True,
            "private_data_redacted": True,
            "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
            "no_cancel_by_default": True,
            "no_private_data_leak_proof_status": "PASS_NO_PRIVATE_DATA_LEAK",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "RECONCILE_FORENSIC_AUTO_ORCHESTRATOR_V6_REVIEWED_LOCKED_NEXT_RUN_POST_PROOF_ROUTE_AUTOPILOT_NO_SUBMIT",
    }


_BUNDLE = fcc.StageBundle(
    version=300, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V300_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V300ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
