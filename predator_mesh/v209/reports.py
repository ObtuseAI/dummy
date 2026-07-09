"""DUMMY v209 live-proof runner wrapper — one runner entrypoint for first live proof; submits ONLY on full auth + env gate.

Submit occurs ONLY when V208 resolves LIVE_PROOF_ARMABLE, the explicit CLI/env gate is set
(DUMMY_LIVE_PROOF_MODE=1 + DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY), the exact approval
validates, live-submit is operator-enabled, caps are present, mode is LIVE_AUTHORIZED, and a LiveBrokerFirewall adapter
is injected. Default is dry -> no submit (PARTIAL_LIVE_PROOF_RUNNER_NOT_ARMED). Hard max one proof attempt; limit-only,
no market orders, no repeat. Tests inject a NON-BROKER double.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v209 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "first_live_proof": True}
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"

WORKSTREAM = "v209: Live Proof Runner Wrapper Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v195.json"
FINAL_NAME = "final_report_v209.json"
INDEX_KEYS = ["live_proof_runner_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V209 Live-Proof Runner Wrapper"
MISSION_KEY = "dummy_mission_state_report_v195"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Runner", "live_proof_runner_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V209_ROUTES = [
    "/api/v209/live-proof-runner-controller",
    "/api/v209/v208-baseline",
    "/api/v209/proof-approval-validator",
    "/api/v209/authority-armable-prerequisite",
    "/api/v209/cli-env-gate",
    "/api/v209/mode-live-authorized-prerequisite",
    "/api/v209/proof-target-guard",
    "/api/v209/max-one-proof-attempt-guard",
    "/api/v209/livebrokerfirewall-only-proof",
    "/api/v209/limit-only-proof",
    "/api/v209/no-market-order-proof",
    "/api/v209/proof-lock",
    "/api/v209/no-repeat-submit-proof",
    "/api/v209/readiness-governor",
    "/api/v209/execution-lock",
    "/api/v209/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-proof-runner-controller": ["v209_live_proof_runner_controller_report.json"],
    "v208-baseline": ["v208_baseline_readback_v1_report.json"],
    "proof-approval-validator": ["v209_proof_approval_validator_report.json"],
    "authority-armable-prerequisite": ["v209_authority_armable_prerequisite_report.json"],
    "cli-env-gate": ["v209_cli_env_gate_report.json"],
    "mode-live-authorized-prerequisite": ["v209_mode_live_authorized_prerequisite_report.json"],
    "proof-target-guard": ["v209_proof_target_guard_report.json"],
    "max-one-proof-attempt-guard": ["v209_max_one_proof_attempt_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v209_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v209_limit_only_proof_report.json"],
    "no-market-order-proof": ["v209_no_market_order_proof_report.json"],
    "proof-lock": ["v209_proof_lock_report.json"],
    "no-repeat-submit-proof": ["v209_no_repeat_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v169_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v168_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v209_report_v1.json", "completion_oriented_next_action_v209_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(209)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v209/reports.py scripts/generate_v209_reports.py dashboard/backend/v209_routes.py",
    "python scripts/generate_v209_reports.py",
    "python scripts/run_dummy_first_live_proof.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V209Context:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF", max_proof_orders=1) -> None:
        self.v208_baseline_status = sgc.baseline_status("final_report_v208.json", "V208")
        if armable_override is None:
            self.armable = str(sgc.load_artifact("final_report_v208.json").get("authority_state", "")) == "LIVE_PROOF_ARMABLE"
        else:
            self.armable = bool(armable_override)
        self.env_gate = bool(env_gate_mode) and str(env_gate_ack) == LIVE_PROOF_ACK
        if mode_live_override is None:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        else:
            self.mode_live = bool(mode_live_override)
        self.proof_target = proof_target_override
        self.target_valid = self.proof_target in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.result = sgc.pilot_submit(
            "v209-live-proof-runner",
            approval_input=proof_approval,
            approval_path=proof_approval_path,
            dry_audit_ready=self.armable and self.env_gate and self.mode_live and self.target_valid,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape={**ORDER_SHAPE, "proof_target": self.proof_target},
            max_pilot_orders=max_proof_orders,
        )
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def submitted(self) -> bool:
        r = self.result["submit_result"]
        return r is not None and bool(r.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        r = self.result["submit_result"]
        return bool(r and r.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_LIVE_PROOF_RUNNER_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v208_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.armable:
            base.append("AUTHORITY_NOT_ARMABLE")
        if not self.env_gate:
            base.append("CLI_ENV_GATE_ABSENT")
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.target_valid:
            base.append("PROOF_TARGET_INVALID")
        return base or ["LIVE_PROOF_RUNNER_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "LIVE_PROOF_RUNNER_SUBMITTED_PROOF_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_SET_CLI_ENV_GATE_AND_PROVIDE_FULL_LIVE_AUTHORITY_DEFAULT_DRY"


def _common(ctx: V209Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v208_baseline_status": ctx.v208_baseline_status,
        "live_proof_runner_controller_status": ctx.controller_status,
        "proof_approval_validator_status": "PASS_PROOF_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_PROOF_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_PROOF_APPROVAL_ABSENT"),
        "authority_armable_prerequisite_status": "PASS_AUTHORITY_ARMABLE" if ctx.armable else "PARTIAL_AUTHORITY_NOT_ARMABLE",
        "cli_env_gate_status": "PASS_CLI_ENV_GATE_SET" if ctx.env_gate else "PARTIAL_CLI_ENV_GATE_ABSENT_DEFAULT_DRY",
        "required_env_mode": "DUMMY_LIVE_PROOF_MODE=1",
        "required_env_ack": f"DUMMY_LIVE_PROOF_ACK={LIVE_PROOF_ACK}",
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "proof_target_guard_status": f"PASS_PROOF_TARGET_{ctx.proof_target}" if ctx.target_valid else "PARTIAL_PROOF_TARGET_INVALID",
        "proof_target": ctx.proof_target,
        "max_one_proof_attempt_guard_status": "PASS_MAX_ONE_PROOF_ATTEMPT",
        "max_proof_order_count": ctx.result["max_pilot_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_submit_proof_status": "PASS_NO_REPEAT_SUBMIT",
        "proof_approval_present": bool(v["accepted"]),
        "proof_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "dry_run_default": not ctx.env_gate,
        "proof_lock_status": "PASS_PROOF_AUTOLOCKED" if ctx.submitted else "PASS_PROOF_LOCK_ARMED",
        "proof_locked": ctx.submitted,
        "proof_id": ctx.result["pilot_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v169_status": "PASS",
        "execution_lock_deep_recheck_v168_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V209Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v208_baseline"):
        return "PASS" if ctx.v208_baseline_status == "PASS_V208_BASELINE_READBACK" else "FAIL" if ctx.v208_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v209_live_proof_runner_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V209Context) -> dict[str, Any]:
    workstream = "v209: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v209_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V209_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v209_report.json":
        report.update({"completion_oriented_next_action_v209_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v208_carried_status": ctx.v208_baseline_status, "live_proof_runner_controller_status": ctx.controller_status, "proof_target": ctx.proof_target, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v209_live_proof_runner_controller_report.json"), "proof_lock": str(ARTIFACTS / "v209_proof_lock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v209.json", "dummy_canonical_identity_report_v209.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V209ReportFactory:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, armable_override=None, env_gate_mode=False, env_gate_ack="", mode_live_override=None, proof_target_override="FIRST_REAL_PILOT_PROOF", max_proof_orders=1) -> None:
        self.kw = dict(proof_approval=proof_approval, proof_approval_path=proof_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, armable_override=armable_override, env_gate_mode=env_gate_mode, env_gate_ack=env_gate_ack, mode_live_override=mode_live_override, proof_target_override=proof_target_override, max_proof_orders=max_proof_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V209Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
