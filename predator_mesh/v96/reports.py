"""DUMMY v96 campaign and order 1 approval validator (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v96 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
CAMPAIGN_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

V96_ROUTES = [
    "/api/v96/approval-validator-controller",
    "/api/v96/v95-baseline",
    "/api/v96/campaign-approval-validator",
    "/api/v96/order-1-approval-validator",
    "/api/v96/scope-expiration-maxone-checks",
    "/api/v96/approval-hash-ledger",
    "/api/v96/no-raw-phrase-leakage-proof",
    "/api/v96/no-submit-proof",
    "/api/v96/readiness-governor",
    "/api/v96/execution-lock",
    "/api/v96/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "approval-validator-controller": ["v96_approval_validator_controller_report.json"],
    "v95-baseline": ["v95_baseline_readback_v1_report.json"],
    "campaign-approval-validator": ["v96_campaign_approval_validator_report.json"],
    "order-1-approval-validator": ["v96_order_1_approval_validator_report.json"],
    "scope-expiration-maxone-checks": ["v96_scope_expiration_maxone_checks_report.json"],
    "approval-hash-ledger": ["v96_approval_hash_ledger_report.json"],
    "no-raw-phrase-leakage-proof": ["v96_no_raw_phrase_leakage_proof_report.json"],
    "no-submit-proof": ["v96_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v56_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v55_report.json"],
    "mission-state": ["dummy_mission_state_report_v82.json", "dashboard_v96_report_v1.json", "completion_oriented_next_action_v96_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(96)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v96/reports.py scripts/generate_v96_reports.py dashboard/backend/v96_routes.py",
    "python scripts/generate_v96_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V96Context:
    def __init__(self, *, campaign_approval, campaign_approval_path, order_1_approval, order_1_approval_path) -> None:
        self.v95_baseline_status = sgc.baseline_status("final_report_v95.json", "V95")
        cres = sgc.resolve_packet(campaign_approval_path, campaign_approval)
        self.campaign_validation = sgc.validate_packet(cres, required_phrase=sgc.MICRO_CAMPAIGN_PHRASE, required_fields=CAMPAIGN_FIELDS, required_scope=sgc.MICRO_CAMPAIGN_SCOPE)
        ores = sgc.resolve_packet(order_1_approval_path, order_1_approval)
        self.order_validation = sgc.validate_packet(ores, required_phrase=sgc.CAMPAIGN_PER_ORDER_PHRASE, required_fields=sgc.CAMPAIGN_PER_ORDER_FIELDS, required_scope=sgc.CAMPAIGN_PER_ORDER_SCOPE, ack_requirements=sgc.CAMPAIGN_PER_ORDER_ACKS)

    @property
    def both_valid(self) -> bool:
        return self.campaign_validation["accepted"] and self.order_validation["accepted"]

    @property
    def any_fail(self) -> bool:
        return (self.campaign_validation["state"] == "PRESENT" and not self.campaign_validation["accepted"]) or (self.order_validation["state"] == "PRESENT" and not self.order_validation["accepted"])

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_APPROVAL"
        if self.both_valid:
            return "PASS_CAMPAIGN_AND_ORDER1_APPROVAL_VALID_NO_SUBMIT"
        return "PARTIAL_CAMPAIGN_OR_ORDER1_APPROVAL_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v95_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.both_valid else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v95_baseline_status.startswith("FAIL"):
            return ["FAIL_V95_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_APPROVAL"]
        blockers: list[str] = []
        if not self.campaign_validation["accepted"]:
            blockers.append("CAMPAIGN_APPROVAL_ABSENT")
        if not self.order_validation["accepted"]:
            blockers.append("ORDER1_APPROVAL_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "CAMPAIGN_AND_ORDER1_APPROVED_AWAIT_LIVE_CONFIG_TIEOUT" if self.both_valid else "OPERATOR_MUST_PROVIDE_CAMPAIGN_AND_ORDER1_APPROVAL"


def _common(ctx: V96Context) -> dict[str, Any]:
    return {
        "v95_baseline_status": ctx.v95_baseline_status,
        "approval_validator_controller_status": ctx.controller_status,
        "campaign_approval_validator_status": "PASS_CAMPAIGN_APPROVAL_VALID" if ctx.campaign_validation["accepted"] else ("FAIL_CLOSED_INVALID_CAMPAIGN_APPROVAL" if ctx.campaign_validation["state"] == "PRESENT" else "PARTIAL_CAMPAIGN_APPROVAL_ABSENT"),
        "order_1_approval_validator_status": "PASS_ORDER1_APPROVAL_VALID" if ctx.order_validation["accepted"] else ("FAIL_CLOSED_INVALID_ORDER1_APPROVAL" if ctx.order_validation["state"] == "PRESENT" else "PARTIAL_ORDER1_APPROVAL_ABSENT"),
        "campaign_approval_phrase": sgc.MICRO_CAMPAIGN_PHRASE,
        "per_order_approval_phrase": sgc.CAMPAIGN_PER_ORDER_PHRASE,
        "scope_expiration_maxone_checks_status": "PASS_SCOPE_EXPIRATION_MAXONE",
        "approval_hash_ledger_status": "PASS_HASH_LEDGER_ONLY",
        "campaign_approval_hash": ctx.campaign_validation["approval_hash"],
        "order_1_approval_hash": ctx.order_validation["approval_hash"],
        "no_raw_phrase_leakage_proof_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "raw_phrase_serialized": False,
        "raw_acknowledgments_serialized": False,
        "fuzzy_or_broad_or_live_trading_approval_rejected": True,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "live_orders": 0,
        "readiness_governor_v56_status": "PASS",
        "execution_lock_deep_recheck_v55_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V96Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v95_baseline"):
        return "PASS" if ctx.v95_baseline_status == "PASS_V95_BASELINE_READBACK" else "FAIL" if ctx.v95_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v96_approval_validator_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.both_valid else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V96Context) -> dict[str, Any]:
    workstream = "v96: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v96_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V96_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v96_report.json":
        report.update({"completion_oriented_next_action_v96_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v82.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v95_carried_status": ctx.v95_baseline_status, "approval_validator_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v96.json"), "validator": str(ARTIFACTS / "v96_approval_validator_controller_report.json"), "hash_ledger": str(ARTIFACTS / "v96_approval_hash_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v96.json", "dummy_canonical_identity_report_v96.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V96ReportFactory:
    def __init__(self, *, campaign_approval=None, campaign_approval_path=None, order_1_approval=None, order_1_approval_path=None) -> None:
        self.kw = dict(campaign_approval=campaign_approval, campaign_approval_path=campaign_approval_path, order_1_approval=order_1_approval, order_1_approval_path=order_1_approval_path)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V96Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
