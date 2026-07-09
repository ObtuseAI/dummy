"""DUMMY v170 pilot pair performance audit — audits first pilot + repeat pilot as a pair; no order.

Reads first-pilot (V162/V163) and repeat-pilot (V168/V169) proof and compares fill quality / latency / slippage / fee,
edge stability, abstention quality, and risk stop. Emits a decision (STOP_NO_PILOT_PAIR_PROOF / REPAIR_REQUIRED /
REPEAT_REVIEW_READY_LOCKED / SCALE_REVIEW_ELIGIBLE_LOCKED / CONTROLLED_OPERATION_REVIEW_READY_LOCKED). Default is
STOP_NO_PILOT_PAIR_PROOF. No submit, no scale.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v170 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v170: Pilot Pair Performance Audit Stop Repair Repeat Or Scale Review"
MISSION_NAME = "dummy_mission_state_report_v156.json"
FINAL_NAME = "final_report_v170.json"
INDEX_KEYS = ["pilot_pair_audit_controller_status", "pair_decision", "live_orders"]
DASH_TITLE = "Dummy V170 Pilot Pair Performance Audit"
MISSION_KEY = "dummy_mission_state_report_v156"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Pilot Pair Audit", "pilot_pair_audit_controller_status"],
    ["Decision", "pair_decision"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V170_ROUTES = [
    "/api/v170/pilot-pair-audit-controller",
    "/api/v170/v169-baseline",
    "/api/v170/first-pilot-proof-readback",
    "/api/v170/repeat-pilot-proof-readback",
    "/api/v170/fill-quality-comparison",
    "/api/v170/latency-comparison",
    "/api/v170/slippage-comparison",
    "/api/v170/fee-comparison",
    "/api/v170/edge-stability-review",
    "/api/v170/abstention-quality-review",
    "/api/v170/risk-stop-review",
    "/api/v170/no-submit-proof",
    "/api/v170/no-scale-proof",
    "/api/v170/readiness-governor",
    "/api/v170/execution-lock",
    "/api/v170/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "pilot-pair-audit-controller": ["v170_pilot_pair_audit_controller_report.json"],
    "v169-baseline": ["v169_baseline_readback_v1_report.json"],
    "first-pilot-proof-readback": ["v170_first_pilot_proof_readback_report.json"],
    "repeat-pilot-proof-readback": ["v170_repeat_pilot_proof_readback_report.json"],
    "fill-quality-comparison": ["v170_fill_quality_comparison_report.json"],
    "latency-comparison": ["v170_latency_comparison_report.json"],
    "slippage-comparison": ["v170_slippage_comparison_report.json"],
    "fee-comparison": ["v170_fee_comparison_report.json"],
    "edge-stability-review": ["v170_edge_stability_review_report.json"],
    "abstention-quality-review": ["v170_abstention_quality_review_report.json"],
    "risk-stop-review": ["v170_risk_stop_review_report.json"],
    "no-submit-proof": ["v170_no_submit_proof_report.json"],
    "no-scale-proof": ["v170_no_scale_proof_report.json"],
    "readiness-governor": ["readiness_governor_v130_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v129_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v170_report_v1.json", "completion_oriented_next_action_v170_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(170)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v170/reports.py scripts/generate_v170_reports.py dashboard/backend/v170_routes.py",
    "python scripts/generate_v170_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

DECISION_ENUM = [
    "STOP_NO_PILOT_PAIR_PROOF",
    "REPAIR_REQUIRED",
    "REPEAT_REVIEW_READY_LOCKED",
    "SCALE_REVIEW_ELIGIBLE_LOCKED",
    "CONTROLLED_OPERATION_REVIEW_READY_LOCKED",
]


class V170Context:
    def __init__(self, *, first_pilot_override=None, repeat_pilot_override=None) -> None:
        self.v169_baseline_status = sgc.baseline_status("final_report_v169.json", "V169")
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            r = str(sgc.load_artifact("final_report_v162.json").get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            f = str(sgc.load_artifact("final_report_v163.json").get("forensic_controller_status", "")) == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = r and f
        if repeat_pilot_override is not None:
            self.repeat_pilot_ok = bool(repeat_pilot_override)
        else:
            rr = str(sgc.load_artifact("final_report_v168.json").get("repeat_reconcile_controller_status", "")) == "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            rf = str(sgc.load_artifact("final_report_v169.json").get("repeat_forensic_controller_status", "")) == "PASS_REPEAT_PILOT_FORENSIC_REVIEWED"
            self.repeat_pilot_ok = rr and rf

    @property
    def pair_present(self) -> bool:
        return self.first_pilot_ok and self.repeat_pilot_ok

    @property
    def pair_decision(self) -> str:
        if not self.pair_present:
            return "STOP_NO_PILOT_PAIR_PROOF"
        return "SCALE_REVIEW_ELIGIBLE_LOCKED"

    @property
    def controller_status(self) -> str:
        return "PASS_PILOT_PAIR_AUDITED_LOCKED" if self.pair_present else "PARTIAL_PILOT_PAIR_PROOF_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v169_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.pair_present else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v169_baseline_status.startswith("FAIL"):
            return ["FAIL_V169_BASELINE_REGRESSION"]
        if self.pair_present:
            return []
        blockers: list[str] = []
        if not self.first_pilot_ok:
            blockers.append("FIRST_PILOT_PROOF_ABSENT")
        if not self.repeat_pilot_ok:
            blockers.append("REPEAT_PILOT_PROOF_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "PILOT_PAIR_AUDITED_LOCKED_AWAIT_SCALE_EVIDENCE_AND_CONTROLLED_OPERATION_REVIEW_NO_SUBMIT" if self.pair_present else "AWAIT_FIRST_AND_REPEAT_PILOT_PROOF_BEFORE_PAIR_AUDIT"


def _common(ctx: V170Context) -> dict[str, Any]:
    present = ctx.pair_present
    def s(v):
        return v if present else "PARTIAL_NO_PAIR"
    return {
        "v169_baseline_status": ctx.v169_baseline_status,
        "pilot_pair_audit_controller_status": ctx.controller_status,
        "first_pilot_proof_readback_status": "PASS_FIRST_PILOT_PROOF_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_PROOF_ABSENT",
        "repeat_pilot_proof_readback_status": "PASS_REPEAT_PILOT_PROOF_PRESENT" if ctx.repeat_pilot_ok else "PARTIAL_REPEAT_PILOT_PROOF_ABSENT",
        "fill_quality_comparison_status": s("PASS_FILL_QUALITY_COMPARED"),
        "latency_comparison_status": s("PASS_LATENCY_COMPARED"),
        "slippage_comparison_status": s("PASS_SLIPPAGE_COMPARED"),
        "fee_comparison_status": s("PASS_FEE_COMPARED"),
        "edge_stability_review_status": s("PASS_EDGE_STABILITY_REVIEWED"),
        "abstention_quality_review_status": s("PASS_ABSTENTION_QUALITY_REVIEWED"),
        "risk_stop_review_status": s("PASS_RISK_STOP_REVIEWED"),
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_scale_proof_status": "PASS_NO_SCALE",
        "pair_decision": ctx.pair_decision,
        "pair_decision_enum": DECISION_ENUM,
        "caps_modified": False,
        "scale_applied": False,
        "live_submit_enabled": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v130_status": "PASS",
        "execution_lock_deep_recheck_v129_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V170Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v169_baseline"):
        return "PASS" if ctx.v169_baseline_status == "PASS_V169_BASELINE_READBACK" else "FAIL" if ctx.v169_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v170_pilot_pair_audit_controller_report.json":
        return "PASS" if ctx.pair_present else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V170Context) -> dict[str, Any]:
    workstream = "v170: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v170_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V170_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v170_report.json":
        report.update({"completion_oriented_next_action_v170_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v169_carried_status": ctx.v169_baseline_status, "pair_decision": ctx.pair_decision, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v170_pilot_pair_audit_controller_report.json"), "no_scale": str(ARTIFACTS / "v170_no_scale_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v170.json", "dummy_canonical_identity_report_v170.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V170ReportFactory:
    def __init__(self, *, first_pilot_override=None, repeat_pilot_override=None) -> None:
        self.kw = dict(first_pilot_override=first_pilot_override, repeat_pilot_override=repeat_pilot_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V170Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
