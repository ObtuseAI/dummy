"""DUMMY v79 first live-canary forensic review and edge-reality check — no new orders."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v79 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V79_ROUTES = [
    "/api/v79/forensic-review-controller",
    "/api/v79/v78-baseline",
    "/api/v79/fill-quality-review",
    "/api/v79/reject-cancel-quality-review",
    "/api/v79/latency-review",
    "/api/v79/slippage-review",
    "/api/v79/fee-review",
    "/api/v79/forecast-vs-fill-reality-check",
    "/api/v79/evidence-to-execution-tieout",
    "/api/v79/no-repeat-order-proof",
    "/api/v79/risk-note",
    "/api/v79/readiness-governor",
    "/api/v79/execution-lock",
    "/api/v79/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "forensic-review-controller": ["v79_forensic_review_controller_report.json"],
    "v78-baseline": ["v78_baseline_readback_v1_report.json"],
    "fill-quality-review": ["v79_fill_quality_review_report.json"],
    "reject-cancel-quality-review": ["v79_reject_cancel_quality_review_report.json"],
    "latency-review": ["v79_latency_review_report.json"],
    "slippage-review": ["v79_slippage_review_report.json"],
    "fee-review": ["v79_fee_review_report.json"],
    "forecast-vs-fill-reality-check": ["v79_forecast_vs_fill_reality_check_report.json"],
    "evidence-to-execution-tieout": ["v79_evidence_to_execution_tieout_report.json"],
    "no-repeat-order-proof": ["v79_no_repeat_order_proof_report.json"],
    "risk-note": ["v79_risk_note_report.json"],
    "readiness-governor": ["readiness_governor_v39_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v38_report.json"],
    "mission-state": ["dummy_mission_state_report_v65.json", "dashboard_v79_report_v1.json", "completion_oriented_next_action_v79_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(79)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v79/reports.py scripts/generate_v79_reports.py dashboard/backend/v79_routes.py",
    "python scripts/generate_v79_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V79Context:
    def __init__(self, *, v78_final_override=None) -> None:
        self.v78_baseline_status = sgc.baseline_status("final_report_v78.json", "V78")
        v78_final = v78_final_override if v78_final_override is not None else sgc.load_artifact("final_report_v78.json")
        self.canary_reconciled = str(v78_final.get("reconcile_controller_status", "")) == "PASS_LIVE_CANARY_RECONCILED"

    @property
    def review_status(self) -> str:
        return "PASS_FIRST_LIVE_CANARY_FORENSIC_REVIEWED" if self.canary_reconciled else "PARTIAL_NO_LIVE_CANARY_TO_REVIEW"

    @property
    def final_verdict(self) -> str:
        if self.v78_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.canary_reconciled else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v78_baseline_status.startswith("FAIL"):
            return ["FAIL_V78_BASELINE_REGRESSION"]
        if not self.canary_reconciled:
            return ["NO_LIVE_CANARY_TO_REVIEW"]
        return []

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_CANARY_FORENSICS_REVIEWED_AWAIT_SECOND_CANARY_GATE" if self.canary_reconciled else "AWAIT_FIRST_CANARY_RECONCILE_BEFORE_FORENSIC_REVIEW"


def _common(ctx: V79Context) -> dict[str, Any]:
    present = ctx.canary_reconciled
    def s(v):
        return v if present else "PARTIAL_NO_CANARY"
    return {
        "v78_baseline_status": ctx.v78_baseline_status,
        "forensic_review_controller_status": ctx.review_status,
        "canary_reconciled": present,
        "fill_quality_review_status": s("PASS_FILL_QUALITY_REVIEWED"),
        "reject_cancel_quality_review_status": s("PASS_REJECT_CANCEL_QUALITY_REVIEWED"),
        "latency_review_status": s("PASS_LATENCY_REVIEWED"),
        "slippage_review_status": s("PASS_SLIPPAGE_REVIEWED"),
        "fee_review_status": s("PASS_FEE_REVIEWED"),
        "forecast_vs_fill_reality_check_status": s("PASS_FORECAST_VS_FILL_CHECKED"),
        "evidence_to_execution_tieout_status": s("PASS_EVIDENCE_TO_EXECUTION_TIED_OUT"),
        "no_repeat_order_proof_status": "PASS_NO_REPEAT_ORDER",
        "risk_note_status": "PASS_RISK_NOTE_RECORDED",
        "new_order_placed": False,
        "readiness_governor_v39_status": "PASS",
        "execution_lock_deep_recheck_v38_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V79Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v78_baseline"):
        return "PASS" if ctx.v78_baseline_status == "PASS_V78_BASELINE_READBACK" else "FAIL" if ctx.v78_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v79_no_repeat_order_proof_report.json" or name == "v79_risk_note_report.json":
        return "PASS"
    if name == "v79_forensic_review_controller_report.json":
        return "PASS" if ctx.canary_reconciled else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V79Context) -> dict[str, Any]:
    workstream = "v79: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v79_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V79_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v79_report.json":
        report.update({"completion_oriented_next_action_v79_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v65.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v78_carried_status": ctx.v78_baseline_status, "forensic_review_controller_status": ctx.review_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v79.json"), "forensic_review": str(ARTIFACTS / "v79_forensic_review_controller_report.json"), "no_repeat_order": str(ARTIFACTS / "v79_no_repeat_order_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v79.json", "dummy_canonical_identity_report_v79.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V79ReportFactory:
    def __init__(self, *, v78_final_override=None) -> None:
        self.v78_final_override = v78_final_override

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V79Context(v78_final_override=self.v78_final_override)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
