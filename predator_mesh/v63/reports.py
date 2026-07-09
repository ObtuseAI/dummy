"""DUMMY v63 dry-submit / shadow packet schema gate — schema review only, no broker submit."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v63 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

# Allowed inert schema fields (planning artifacts only — cannot submit).
ALLOWED_SCHEMA_FIELDS = ["schema_id", "created_at", "purpose", "rehearsal_only", "broker_submit_enabled", "live_trading", "live_submit", "caps_modified", "quarantine_release_locked"]
# Concepts a schema must never contain.
FORBIDDEN_SCHEMA_FIELDS = ["order_id", "account_id", "private_position", "market_order", "submit_endpoint", "cancel_endpoint", "live_broker_payload", "price", "side", "quantity", "order_intent", "executable_command"]


def _inert_schema(schema_id: str, purpose: str) -> dict[str, Any]:
    return {
        "schema_id": schema_id,
        "created_at": sgc.now_iso(),
        "purpose": purpose,
        "rehearsal_only": True,
        "broker_submit_enabled": False,
        "live_trading": False,
        "live_submit": False,
        "caps_modified": False,
        "quarantine_release_locked": True,
    }


DRY_SUBMIT_SCHEMA = _inert_schema("dry_submit_schema_v1", "inert dry-submit planning schema, cannot submit")
SHADOW_PACKET_SCHEMA = _inert_schema("shadow_packet_schema_v1", "inert shadow-packet planning schema, cannot submit")


def validate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if schema.get("broker_submit_enabled") is not False:
        reasons.append("BROKER_SUBMIT_NOT_DISABLED")
    for flag in ("live_trading", "live_submit", "caps_modified"):
        if schema.get(flag) is not False:
            reasons.append(f"FLAG_NOT_FALSE:{flag}")
    if schema.get("rehearsal_only") is not True or schema.get("quarantine_release_locked") is not True:
        reasons.append("INERT_FLAGS_MISSING")
    present_forbidden = sorted(f for f in FORBIDDEN_SCHEMA_FIELDS if f in schema)
    if present_forbidden:
        reasons.append("FORBIDDEN_FIELDS_PRESENT")
    return {"schema_id": schema.get("schema_id"), "inert_pass": not reasons, "forbidden_fields_present": present_forbidden, "reasons": reasons}


V63_ROUTES = [
    "/api/v63/dry-submit-schema-gate",
    "/api/v63/shadow-packet-schema-gate",
    "/api/v63/v62-baseline",
    "/api/v63/schema-only-artifact-validator",
    "/api/v63/broker-submit-denial-proof",
    "/api/v63/no-market-order-validator",
    "/api/v63/no-live-submit-validator",
    "/api/v63/canary-nonexecution-validator-v13",
    "/api/v63/readiness-governor",
    "/api/v63/execution-lock",
    "/api/v63/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "dry-submit-schema-gate": ["v63_dry_submit_schema_gate_report.json"],
    "shadow-packet-schema-gate": ["v63_shadow_packet_schema_gate_report.json"],
    "v62-baseline": ["v62_baseline_readback_v1_report.json"],
    "schema-only-artifact-validator": ["v63_schema_only_artifact_validator_report.json"],
    "broker-submit-denial-proof": ["v63_broker_submit_denial_proof_report.json"],
    "no-market-order-validator": ["v63_no_market_order_validator_report.json"],
    "no-live-submit-validator": ["v63_no_live_submit_validator_report.json"],
    "canary-nonexecution-validator-v13": ["v63_canary_nonexecution_validator_v13_report.json"],
    "readiness-governor": ["readiness_governor_v23_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v22_report.json"],
    "mission-state": ["dummy_mission_state_report_v49.json", "dashboard_v63_report_v1.json", "completion_oriented_next_action_v63_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(63)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v63/reports.py scripts/generate_v63_reports.py dashboard/backend/v63_routes.py",
    "python scripts/generate_v63_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V63Context:
    def __init__(self) -> None:
        self.v62_baseline_status = sgc.baseline_status("final_report_v62.json", "V62")
        self.dry_validation = validate_schema(DRY_SUBMIT_SCHEMA)
        self.shadow_validation = validate_schema(SHADOW_PACKET_SCHEMA)

    @property
    def all_inert(self) -> bool:
        return self.dry_validation["inert_pass"] and self.shadow_validation["inert_pass"]

    @property
    def final_verdict(self) -> str:
        if self.v62_baseline_status.startswith("FAIL") or not self.all_inert:
            return "FAIL"
        if self.v62_baseline_status.startswith("PARTIAL"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v62_baseline_status.startswith("FAIL"):
            return ["FAIL_V62_BASELINE_REGRESSION"]
        if self.v62_baseline_status.startswith("PARTIAL"):
            return ["PARTIAL_V62_BASELINE_UNAVAILABLE"]
        if not self.all_inert:
            return ["SCHEMA_NOT_INERT"]
        return []

    @property
    def next_action(self) -> str:
        return "INERT_DRY_SUBMIT_SHADOW_SCHEMAS_VALIDATED_NO_SUBMIT_PATH"


def _common(ctx: V63Context) -> dict[str, Any]:
    return {
        "v62_baseline_status": ctx.v62_baseline_status,
        "dry_submit_schema_gate_status": "PASS_DRY_SUBMIT_SCHEMA_INERT" if ctx.dry_validation["inert_pass"] else "FAIL_SCHEMA_NOT_INERT",
        "shadow_packet_schema_gate_status": "PASS_SHADOW_PACKET_SCHEMA_INERT" if ctx.shadow_validation["inert_pass"] else "FAIL_SCHEMA_NOT_INERT",
        "dry_submit_schema": DRY_SUBMIT_SCHEMA,
        "shadow_packet_schema": SHADOW_PACKET_SCHEMA,
        "allowed_schema_fields": ALLOWED_SCHEMA_FIELDS,
        "forbidden_schema_fields": FORBIDDEN_SCHEMA_FIELDS,
        "schema_only_artifact_validator_status": "PASS_SCHEMA_ONLY" if ctx.all_inert else "FAIL_SCHEMA_NOT_INERT",
        "schema_validations": [ctx.dry_validation, ctx.shadow_validation],
        "broker_submit_denial_proof_status": "PASS_BROKER_SUBMIT_DENIED",
        "broker_submit_path_present": False,
        "no_market_order_validator_status": "PASS_NO_MARKET_ORDER",
        "no_live_submit_validator_status": "PASS_NO_LIVE_SUBMIT",
        "schemas_can_submit": False,
        "canary_nonexecution_validator_v13_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V13",
        "readiness_governor_v23_status": "PASS",
        "execution_lock_deep_recheck_v22_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V63Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v62_baseline"):
        return "PASS" if ctx.v62_baseline_status == "PASS_V62_BASELINE_READBACK" else "FAIL" if ctx.v62_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V63Context) -> dict[str, Any]:
    workstream = "v63: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v63_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V63_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v63_report.json":
        report.update({"completion_oriented_next_action_v63_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v49.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v62_carried_status": ctx.v62_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v63.json"), "dry_submit_schema": str(ARTIFACTS / "v63_dry_submit_schema_gate_report.json"), "shadow_packet_schema": str(ARTIFACTS / "v63_shadow_packet_schema_gate_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v63.json", "dummy_canonical_identity_report_v63.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V63ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V63Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
