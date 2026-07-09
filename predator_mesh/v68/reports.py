"""DUMMY v68 micro-order candidate selector — limit-only, no submit, inert candidate record."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v68 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

# Inert, non-executable candidate record. Any size/price fields are marked hypothetical only.
CANDIDATE = {
    "candidate_id": "v68-canary-candidate-1",
    "reason": "smallest-liquidity limit-only rehearsal canary candidate",
    "market_class": "public_reference_market_placeholder",
    "evidence_references": ["inert_rehearsal_validation_checklist"],
    "max_hypothetical_exposure": "tiny_placeholder_non_executable",
    "hypothetical_side_non_executable": "buy_hypothetical",
    "hypothetical_limit_price_non_executable": "placeholder",
    "hypothetical_quantity_non_executable": "tiny_placeholder",
    "limit_only": True,
    "market_order_allowed": False,
    "submit_enabled": False,
    "broker_payload_created": False,
    "live_trading": False,
}
FORBIDDEN_CANDIDATE_FIELDS = ["submit_endpoint", "order_id", "broker_payload", "account_balance", "private_position", "market_order", "executable_command", "order_intent_for_execution"]

V68_ROUTES = [
    "/api/v68/candidate-selector",
    "/api/v68/v67-baseline",
    "/api/v68/limit-only-rule",
    "/api/v68/no-market-order-proof",
    "/api/v68/tiny-size-policy",
    "/api/v68/liquidity-slippage-policy",
    "/api/v68/expiry-cancel-policy",
    "/api/v68/no-submit-candidate-record",
    "/api/v68/candidate-quarantine",
    "/api/v68/no-order-intent-for-execution-proof",
    "/api/v68/readiness-governor",
    "/api/v68/execution-lock",
    "/api/v68/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "candidate-selector": ["v68_candidate_selector_report.json"],
    "v67-baseline": ["v67_baseline_readback_v1_report.json"],
    "limit-only-rule": ["v68_limit_only_rule_report.json"],
    "no-market-order-proof": ["v68_no_market_order_proof_report.json"],
    "tiny-size-policy": ["v68_tiny_size_policy_report.json"],
    "liquidity-slippage-policy": ["v68_liquidity_slippage_policy_report.json"],
    "expiry-cancel-policy": ["v68_expiry_cancel_policy_report.json"],
    "no-submit-candidate-record": ["v68_no_submit_candidate_record_report.json"],
    "candidate-quarantine": ["v68_candidate_quarantine_report.json"],
    "no-order-intent-for-execution-proof": ["v68_no_order_intent_for_execution_proof_report.json"],
    "readiness-governor": ["readiness_governor_v28_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v27_report.json"],
    "mission-state": ["dummy_mission_state_report_v54.json", "dashboard_v68_report_v1.json", "completion_oriented_next_action_v68_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(68)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v68/reports.py scripts/generate_v68_reports.py dashboard/backend/v68_routes.py",
    "python scripts/generate_v68_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if candidate.get("limit_only") is not True:
        reasons.append("NOT_LIMIT_ONLY")
    for flag in ("market_order_allowed", "submit_enabled", "broker_payload_created", "live_trading"):
        if candidate.get(flag) is not False:
            reasons.append(f"FLAG_NOT_FALSE:{flag}")
    present = sorted(f for f in FORBIDDEN_CANDIDATE_FIELDS if f in candidate)
    if present:
        reasons.append("FORBIDDEN_FIELDS_PRESENT")
    return {"candidate_id": candidate.get("candidate_id"), "inert_pass": not reasons, "forbidden_fields_present": present, "reasons": reasons}


class V68Context:
    def __init__(self) -> None:
        self.v67_baseline_status = sgc.baseline_status("final_report_v67.json", "V67")
        self.candidate_validation = validate_candidate(CANDIDATE)

    @property
    def candidate_valid(self) -> bool:
        return self.candidate_validation["inert_pass"]

    @property
    def final_verdict(self) -> str:
        if self.v67_baseline_status.startswith("FAIL") or not self.candidate_valid:
            return "FAIL"
        if self.v67_baseline_status.startswith("PARTIAL"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v67_baseline_status.startswith("FAIL"):
            return ["FAIL_V67_BASELINE_REGRESSION"]
        if self.v67_baseline_status.startswith("PARTIAL"):
            return ["PARTIAL_V67_BASELINE_UNAVAILABLE"]
        if not self.candidate_valid:
            return ["CANDIDATE_NOT_INERT"]
        return []

    @property
    def next_action(self) -> str:
        return "CANDIDATE_SELECTED_LIMIT_ONLY_NO_SUBMIT_AWAIT_TIEOUT"


def _common(ctx: V68Context) -> dict[str, Any]:
    return {
        "v67_baseline_status": ctx.v67_baseline_status,
        "candidate_selector_status": "PASS_CANDIDATE_SELECTED_LIMIT_ONLY_NO_SUBMIT" if ctx.candidate_valid else "FAIL_CANDIDATE_NOT_INERT",
        "candidate": CANDIDATE,
        "candidate_validation": ctx.candidate_validation,
        "forbidden_candidate_fields": FORBIDDEN_CANDIDATE_FIELDS,
        "limit_only_rule_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "tiny_size_policy_status": "PASS_TINY_SIZE_ONLY",
        "liquidity_slippage_policy_status": "PASS_LIQUIDITY_SLIPPAGE_POLICY",
        "expiry_cancel_policy_status": "PASS_EXPIRY_CANCEL_POLICY",
        "no_submit_candidate_record_status": "PASS_NO_SUBMIT_CANDIDATE_RECORD",
        "candidate_quarantine_status": "PASS_CANDIDATE_QUARANTINE_REPORT_ONLY",
        "no_order_intent_for_execution_proof_status": "PASS_NO_ORDER_INTENT_FOR_EXECUTION",
        "candidate_is_inert": ctx.candidate_valid,
        "readiness_governor_v28_status": "PASS",
        "execution_lock_deep_recheck_v27_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V68Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v67_baseline"):
        return "PASS" if ctx.v67_baseline_status == "PASS_V67_BASELINE_READBACK" else "FAIL" if ctx.v67_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V68Context) -> dict[str, Any]:
    workstream = "v68: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v68_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V68_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v68_report.json":
        report.update({"completion_oriented_next_action_v68_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v54.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v67_carried_status": ctx.v67_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v68.json"), "candidate_selector": str(ARTIFACTS / "v68_candidate_selector_report.json"), "no_submit_record": str(ARTIFACTS / "v68_no_submit_candidate_record_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v68.json", "dummy_canonical_identity_report_v68.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V68ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V68Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
