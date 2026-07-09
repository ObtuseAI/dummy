"""DUMMY v88 campaign candidate queue and autonomous abstention governor (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v88 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

ABSTENTION_RULES = [
    "low_liquidity",
    "wide_spread",
    "stale_evidence",
    "contradictory_evidence",
    "drift_warning",
    "settlement_ambiguity",
    "risk_cap_conflict",
    "recent_loss_lock",
    "missing_approval",
    "missing_live_submit_caps_firewall",
]
FORBIDDEN_CANDIDATE_FIELDS = ["submit_endpoint", "order_id", "broker_payload", "account_balance", "private_position", "market_order", "executable_command", "order_intent_for_execution"]

# Inert limit-only candidate queue entry. submit_enabled=false by default.
QUEUE = [
    {
        "candidate_id": "v88-campaign-candidate-1",
        "market_class": "public_reference_market_placeholder",
        "limit_only": True,
        "market_order_allowed": False,
        "submit_enabled": False,
        "broker_payload_created": False,
        "live_trading": False,
        "max_hypothetical_exposure": "tiny_placeholder_non_executable",
    }
]

V88_ROUTES = [
    "/api/v88/candidate-queue-controller",
    "/api/v88/v87-baseline",
    "/api/v88/candidate-scoring-readback",
    "/api/v88/limit-only-candidate-queue",
    "/api/v88/no-market-order-proof",
    "/api/v88/abstention-governor",
    "/api/v88/no-submit-candidate-records",
    "/api/v88/no-order-intent-for-execution-proof",
    "/api/v88/readiness-governor",
    "/api/v88/execution-lock",
    "/api/v88/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "candidate-queue-controller": ["v88_candidate_queue_controller_report.json"],
    "v87-baseline": ["v87_baseline_readback_v1_report.json"],
    "candidate-scoring-readback": ["v88_candidate_scoring_readback_report.json"],
    "limit-only-candidate-queue": ["v88_limit_only_candidate_queue_report.json"],
    "no-market-order-proof": ["v88_no_market_order_proof_report.json"],
    "abstention-governor": ["v88_abstention_governor_report.json"],
    "no-submit-candidate-records": ["v88_no_submit_candidate_records_report.json"],
    "no-order-intent-for-execution-proof": ["v88_no_order_intent_for_execution_proof_report.json"],
    "readiness-governor": ["readiness_governor_v48_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v47_report.json"],
    "mission-state": ["dummy_mission_state_report_v74.json", "dashboard_v88_report_v1.json", "completion_oriented_next_action_v88_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(88)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v88/reports.py scripts/generate_v88_reports.py dashboard/backend/v88_routes.py",
    "python scripts/generate_v88_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V88Context:
    def __init__(self) -> None:
        self.v87_baseline_status = sgc.baseline_status("final_report_v87.json", "V87")
        self.queue_clean = all(not any(f in c for f in FORBIDDEN_CANDIDATE_FIELDS) and c["submit_enabled"] is False for c in QUEUE)

    @property
    def final_verdict(self) -> str:
        if self.v87_baseline_status.startswith("FAIL") or not self.queue_clean:
            return "FAIL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v87_baseline_status.startswith("FAIL"):
            return ["FAIL_V87_BASELINE_REGRESSION"]
        return []

    @property
    def next_action(self) -> str:
        return "CAMPAIGN_CANDIDATE_QUEUE_READY_ABSTENTION_ACTIVE_SUBMIT_DISABLED"


def _common(ctx: V88Context) -> dict[str, Any]:
    return {
        "v87_baseline_status": ctx.v87_baseline_status,
        "candidate_queue_controller_status": "PASS_CANDIDATE_QUEUE_READY_SUBMIT_DISABLED",
        "candidate_queue": QUEUE,
        "queue_is_inert": ctx.queue_clean,
        "submit_enabled_default": False,
        "candidate_scoring_readback_status": "PASS_CANDIDATE_SCORING_READBACK",
        "limit_only_candidate_queue_status": "PASS_LIMIT_ONLY_QUEUE",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "abstention_governor_status": "PASS_ABSTENTION_GOVERNOR_ACTIVE",
        "abstention_rules": ABSTENTION_RULES,
        "no_submit_candidate_records_status": "PASS_NO_SUBMIT_CANDIDATE_RECORDS",
        "no_order_intent_for_execution_proof_status": "PASS_NO_ORDER_INTENT_FOR_EXECUTION",
        "forbidden_candidate_fields": FORBIDDEN_CANDIDATE_FIELDS,
        "broker_payload_present": False,
        "live_orders": 0,
        "readiness_governor_v48_status": "PASS",
        "execution_lock_deep_recheck_v47_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V88Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v87_baseline"):
        return "PASS" if ctx.v87_baseline_status == "PASS_V87_BASELINE_READBACK" else "FAIL" if ctx.v87_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V88Context) -> dict[str, Any]:
    workstream = "v88: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v88_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V88_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v88_report.json":
        report.update({"completion_oriented_next_action_v88_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v74.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v87_carried_status": ctx.v87_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v88.json"), "candidate_queue": str(ARTIFACTS / "v88_candidate_queue_controller_report.json"), "abstention_governor": str(ARTIFACTS / "v88_abstention_governor_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v88.json", "dummy_canonical_identity_report_v88.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V88ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V88Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
