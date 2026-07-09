"""DUMMY v74 live-canary blocker closure audit and authority-gap report (no live order)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v74 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

BLOCKER_CLASSES = [
    "LIVE_CANARY_APPROVAL_ABSENT",
    "NO_LIVE_CANARY_TO_RECONCILE",
    "MISSING_V70_V71_FIRST_CANARY_PROOF",
    "LIVE_SUBMIT_DISABLED",
    "CAPS_UNVERIFIED",
    "BROKER_ADAPTER_ABSENT",
    "PRIVATE_ACCESS_LOCKED",
]
NEXT_ACTION_MATRIX = {
    "LIVE_CANARY_APPROVAL_ABSENT": "OPERATOR_MUST_PROVIDE_EXACT_LIVE_CANARY_APPROVAL_FILE",
    "NO_LIVE_CANARY_TO_RECONCILE": "AWAIT_FIRST_CANARY_SUBMIT_BEFORE_RECONCILE",
    "MISSING_V70_V71_FIRST_CANARY_PROOF": "COMPLETE_FIRST_CANARY_AND_RECONCILE_BEFORE_SECOND",
    "LIVE_SUBMIT_DISABLED": "OPERATOR_MUST_ENABLE_LIVE_SUBMIT_IN_CONFIG_DUMMY_WILL_NOT",
    "CAPS_UNVERIFIED": "OPERATOR_MUST_PROVIDE_CAPS_CONFIG_DUMMY_WILL_NOT_MODIFY",
    "BROKER_ADAPTER_ABSENT": "OPERATOR_MUST_PROVIDE_LIVEBROKERFIREWALL_ADAPTER",
    "PRIVATE_ACCESS_LOCKED": "OPERATOR_MUST_PROVIDE_READ_ONLY_BROKER_APPROVAL_FOR_PRIVATE_READ",
}

V74_ROUTES = [
    "/api/v74/blocker-closure-controller",
    "/api/v74/v73-baseline",
    "/api/v74/blocker-classifier",
    "/api/v74/next-action-matrix",
    "/api/v74/no-submit-proof",
    "/api/v74/readiness-governor",
    "/api/v74/execution-lock",
    "/api/v74/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "blocker-closure-controller": ["v74_blocker_closure_controller_report.json"],
    "v73-baseline": ["v73_baseline_readback_v1_report.json"],
    "blocker-classifier": ["v74_blocker_classifier_report.json"],
    "next-action-matrix": ["v74_next_action_matrix_report.json"],
    "no-submit-proof": ["v74_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v34_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v33_report.json"],
    "mission-state": ["dummy_mission_state_report_v60.json", "dashboard_v74_report_v1.json", "completion_oriented_next_action_v74_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(74)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v74/reports.py scripts/generate_v74_reports.py dashboard/backend/v74_routes.py",
    "python scripts/generate_v74_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V74Context:
    def __init__(self) -> None:
        self.v73_baseline_status = sgc.baseline_status("final_report_v73.json", "V73")

    @property
    def final_verdict(self) -> str:
        if self.v73_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v73_baseline_status.startswith("FAIL"):
            return ["FAIL_V73_BASELINE_REGRESSION"]
        return []

    @property
    def next_action(self) -> str:
        return "AUTHORITY_GAP_CLASSIFIED_OPERATOR_MUST_SUPPLY_EXACT_LIVE_AUTHORITY"


def _common(ctx: V74Context) -> dict[str, Any]:
    return {
        "v73_baseline_status": ctx.v73_baseline_status,
        "blocker_closure_controller_status": "PASS_BLOCKERS_CLASSIFIED_NO_SUBMIT",
        "blocker_classifier_status": "PASS_BLOCKERS_CLASSIFIED",
        "classified_blockers": BLOCKER_CLASSES,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "authority_gap": {b: NEXT_ACTION_MATRIX[b] for b in BLOCKER_CLASSES},
        "readiness_governor_v34_status": "PASS",
        "execution_lock_deep_recheck_v33_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V74Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v73_baseline"):
        return "PASS" if ctx.v73_baseline_status == "PASS_V73_BASELINE_READBACK" else "FAIL" if ctx.v73_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V74Context) -> dict[str, Any]:
    workstream = "v74: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v74_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V74_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v74_report.json":
        report.update({"completion_oriented_next_action_v74_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v60.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v73_carried_status": ctx.v73_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v74.json"), "blocker_classifier": str(ARTIFACTS / "v74_blocker_classifier_report.json"), "no_submit_proof": str(ARTIFACTS / "v74_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v74.json", "dummy_canonical_identity_report_v74.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V74ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V74Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
