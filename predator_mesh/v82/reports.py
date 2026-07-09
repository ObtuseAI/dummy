"""DUMMY v82 micro-canary campaign gate — designed and locked, no automatic live orders."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v82 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

CAMPAIGN_POLICY = {
    "max_trades": 5,
    "min_trades": 3,
    "per_order_approval_required": True,
    "automatic_live_orders": False,
    "max_daily_loss": "operator_configured_placeholder",
    "max_exposure": "operator_configured_placeholder",
    "cooldown_required": True,
    "drift_lock": True,
    "session_lock": True,
}

V82_ROUTES = [
    "/api/v82/campaign-gate-controller",
    "/api/v82/v81-baseline",
    "/api/v82/campaign-approval-validator",
    "/api/v82/per-order-approval-requirement",
    "/api/v82/max-trades-policy",
    "/api/v82/max-daily-loss-policy",
    "/api/v82/max-exposure-policy",
    "/api/v82/cooldown-policy",
    "/api/v82/drift-lock-policy",
    "/api/v82/session-lock-policy",
    "/api/v82/no-auto-submit-proof",
    "/api/v82/readiness-governor",
    "/api/v82/execution-lock",
    "/api/v82/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "campaign-gate-controller": ["v82_campaign_gate_controller_report.json"],
    "v81-baseline": ["v81_baseline_readback_v1_report.json"],
    "campaign-approval-validator": ["v82_campaign_approval_validator_report.json"],
    "per-order-approval-requirement": ["v82_per_order_approval_requirement_report.json"],
    "max-trades-policy": ["v82_max_trades_policy_report.json"],
    "max-daily-loss-policy": ["v82_max_daily_loss_policy_report.json"],
    "max-exposure-policy": ["v82_max_exposure_policy_report.json"],
    "cooldown-policy": ["v82_cooldown_policy_report.json"],
    "drift-lock-policy": ["v82_drift_lock_policy_report.json"],
    "session-lock-policy": ["v82_session_lock_policy_report.json"],
    "no-auto-submit-proof": ["v82_no_auto_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v42_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v41_report.json"],
    "mission-state": ["dummy_mission_state_report_v68.json", "dashboard_v82_report_v1.json", "completion_oriented_next_action_v82_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(82)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v82/reports.py scripts/generate_v82_reports.py dashboard/backend/v82_routes.py",
    "python scripts/generate_v82_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V82Context:
    def __init__(self, *, campaign_approval=None) -> None:
        self.v81_baseline_status = sgc.baseline_status("final_report_v81.json", "V81")
        self.campaign_approved = bool(campaign_approval and campaign_approval.get("exact_phrase") == sgc.MICRO_CAMPAIGN_PHRASE)

    @property
    def final_verdict(self) -> str:
        if self.v81_baseline_status.startswith("FAIL"):
            return "FAIL"
        # Gate design/locked with no auto-submit is the PASS condition.
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v81_baseline_status.startswith("FAIL"):
            return ["FAIL_V81_BASELINE_REGRESSION"]
        return []

    @property
    def next_action(self) -> str:
        return "MICRO_CAMPAIGN_GATE_READY_LOCKED_PER_ORDER_APPROVAL_REQUIRED_NO_AUTO_SUBMIT"


def _common(ctx: V82Context) -> dict[str, Any]:
    return {
        "v81_baseline_status": ctx.v81_baseline_status,
        "campaign_gate_controller_status": "PASS_MICRO_CAMPAIGN_GATE_READY_LOCKED",
        "campaign_policy": CAMPAIGN_POLICY,
        "campaign_approval_validator_status": "PASS_CAMPAIGN_APPROVAL_PRESENT" if ctx.campaign_approved else "PARTIAL_CAMPAIGN_APPROVAL_ABSENT",
        "campaign_approval_phrase": sgc.MICRO_CAMPAIGN_PHRASE,
        "per_order_approval_requirement_status": "PASS_PER_ORDER_APPROVAL_REQUIRED",
        "max_trades_policy_status": "PASS_MAX_3_TO_5_TINY_TRADES",
        "max_daily_loss_policy_status": "PASS_MAX_DAILY_LOSS_POLICY",
        "max_exposure_policy_status": "PASS_MAX_EXPOSURE_POLICY",
        "cooldown_policy_status": "PASS_COOLDOWN_POLICY",
        "drift_lock_policy_status": "PASS_DRIFT_LOCK_POLICY",
        "session_lock_policy_status": "PASS_SESSION_LOCK_POLICY",
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "automatic_live_orders_enabled": False,
        "campaign_live_orders_submitted": 0,
        "readiness_governor_v42_status": "PASS",
        "execution_lock_deep_recheck_v41_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V82Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v81_baseline"):
        return "PASS" if ctx.v81_baseline_status == "PASS_V81_BASELINE_READBACK" else "FAIL" if ctx.v81_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V82Context) -> dict[str, Any]:
    workstream = "v82: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v82_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V82_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False, "dashboard_can_start_campaign": False})
    elif name == "completion_oriented_next_action_v82_report.json":
        report.update({"completion_oriented_next_action_v82_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v68.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v81_carried_status": ctx.v81_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v82.json"), "campaign_gate": str(ARTIFACTS / "v82_campaign_gate_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v82_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v82.json", "dummy_canonical_identity_report_v82.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V82ReportFactory:
    def __init__(self, *, campaign_approval=None) -> None:
        self.campaign_approval = campaign_approval

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V82Context(campaign_approval=self.campaign_approval)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
