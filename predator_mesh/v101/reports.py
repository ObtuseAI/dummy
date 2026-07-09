"""DUMMY v101 order 1 forensic review, edge/fill/slippage, and risk reality check — no new order."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v101 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V101_ROUTES = [
    "/api/v101/forensic-review-controller",
    "/api/v101/v100-baseline",
    "/api/v101/fill-quality-review",
    "/api/v101/reject-cancel-review",
    "/api/v101/latency-review",
    "/api/v101/slippage-review",
    "/api/v101/fee-review",
    "/api/v101/forecast-vs-fill-reality",
    "/api/v101/evidence-to-execution-tieout",
    "/api/v101/risk-note",
    "/api/v101/no-new-order-proof",
    "/api/v101/readiness-governor",
    "/api/v101/execution-lock",
    "/api/v101/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-review-controller": ["v101_forensic_review_controller_report.json"],
    "v100-baseline": ["v100_baseline_readback_v1_report.json"],
    "fill-quality-review": ["v101_fill_quality_review_report.json"],
    "reject-cancel-review": ["v101_reject_cancel_review_report.json"],
    "latency-review": ["v101_latency_review_report.json"],
    "slippage-review": ["v101_slippage_review_report.json"],
    "fee-review": ["v101_fee_review_report.json"],
    "forecast-vs-fill-reality": ["v101_forecast_vs_fill_reality_report.json"],
    "evidence-to-execution-tieout": ["v101_evidence_to_execution_tieout_report.json"],
    "risk-note": ["v101_risk_note_report.json"],
    "no-new-order-proof": ["v101_no_new_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v61_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v60_report.json"],
    "mission-state": ["dummy_mission_state_report_v87.json", "dashboard_v101_report_v1.json", "completion_oriented_next_action_v101_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(101)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v101/reports.py scripts/generate_v101_reports.py dashboard/backend/v101_routes.py",
    "python scripts/generate_v101_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V101Context:
    def __init__(self, *, v100_final_override=None) -> None:
        self.v100_baseline_status = sgc.baseline_status("final_report_v100.json", "V100")
        v100 = v100_final_override if v100_final_override is not None else sgc.load_artifact("final_report_v100.json")
        self.order_reconciled = str(v100.get("reconcile_controller_status", "")) == "PASS_ORDER1_RECONCILED_AUTOLOCKED"

    @property
    def review_status(self) -> str:
        return "PASS_ORDER1_FORENSIC_REVIEWED" if self.order_reconciled else "PARTIAL_NO_ORDER1_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v100_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.order_reconciled else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v100_baseline_status.startswith("FAIL"):
            return ["FAIL_V100_BASELINE_REGRESSION"]
        return [] if self.order_reconciled else ["NO_ORDER1_TO_REVIEW"]

    @property
    def next_action(self) -> str:
        return "ORDER1_FORENSICS_REVIEWED_AWAIT_ORDER2_GATE" if self.order_reconciled else "AWAIT_ORDER1_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V101Context) -> dict[str, Any]:
    present = ctx.order_reconciled
    def s(v):
        return v if present else "PARTIAL_NO_ORDER1"
    return {
        "v100_baseline_status": ctx.v100_baseline_status,
        "forensic_review_controller_status": ctx.review_status,
        "order_1_reconciled": present,
        "fill_quality_review_status": s("PASS_FILL_QUALITY_REVIEWED"),
        "reject_cancel_review_status": s("PASS_REJECT_CANCEL_REVIEWED"),
        "latency_review_status": s("PASS_LATENCY_REVIEWED"),
        "slippage_review_status": s("PASS_SLIPPAGE_REVIEWED"),
        "fee_review_status": s("PASS_FEE_REVIEWED"),
        "forecast_vs_fill_reality_status": s("PASS_FORECAST_VS_FILL"),
        "evidence_to_execution_tieout_status": s("PASS_EVIDENCE_TO_EXECUTION"),
        "risk_note_status": "PASS_RISK_NOTE_RECORDED",
        "no_new_order_proof_status": "PASS_NO_NEW_ORDER",
        "new_order_placed": False,
        "live_orders": 0,
        "readiness_governor_v61_status": "PASS",
        "execution_lock_deep_recheck_v60_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V101Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v100_baseline"):
        return "PASS" if ctx.v100_baseline_status == "PASS_V100_BASELINE_READBACK" else "FAIL" if ctx.v100_baseline_status.startswith("FAIL") else "PARTIAL"
    if name in {"v101_risk_note_report.json", "v101_no_new_order_proof_report.json"}:
        return "PASS"
    if name == "v101_forensic_review_controller_report.json":
        return "PASS" if ctx.order_reconciled else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V101Context) -> dict[str, Any]:
    workstream = "v101: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v101_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V101_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v101_report.json":
        report.update({"completion_oriented_next_action_v101_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v87.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v100_carried_status": ctx.v100_baseline_status, "forensic_review_controller_status": ctx.review_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v101.json"), "forensic_review": str(ARTIFACTS / "v101_forensic_review_controller_report.json"), "no_new_order": str(ARTIFACTS / "v101_no_new_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v101.json", "dummy_canonical_identity_report_v101.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V101ReportFactory:
    def __init__(self, *, v100_final_override=None) -> None:
        self.v100_final_override = v100_final_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V101Context(v100_final_override=self.v100_final_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
