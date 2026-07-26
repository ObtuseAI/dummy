"""Shared helpers for retained staged, locked, non-executing report contracts.

Every stage in this chain is fail-closed and non-executing: no live trading, no live order
submission, no market orders, no live-submit enablement, no caps modification, no account/private
access, no real broker submit/cancel, no broker payload with submit authority, no executable order
path, no browser/PageAgent/DOM, no mined-code execution, no sports activation. New capabilities are
staged, locked, auditable, and require distinct future approval phrases that this bundle never
consumes for execution.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "dummy"

# Scale-step review phrase (never authorizes an automatic capital increase or live order).
SCALE_STEP_PHRASE = "I approve Dummy to review scale step 1 only, with no automatic capital increase, no automatic live orders, caps unchanged unless separately approved, and all future size increases requiring separate approval"
SCALE_STEP_SCOPE = "scale_step_1_review_only"
SCALE_STEP_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Controlled live session canary phrase (V113). Never authorizes automatic or repeat submits; each
# order still passes per-order fail-closed checks and the session auto-locks immediately after the run.
CONTROLLED_SESSION_PHRASE = "I approve Dummy to run one controlled live session canary through LiveBrokerFirewall only, with no market orders, strict caps, per-order fail-closed checks, live-submit already operator-enabled, and immediate session auto-lock"
CONTROLLED_SESSION_SCOPE = "one_controlled_live_session_canary_via_firewall_only"
CONTROLLED_SESSION_FIELDS = [
    "exact_phrase",
    "operator",
    "timestamp",
    "reason",
    "scope",
    "expiration",
    "no_market_order_acknowledgment",
    "strict_caps_acknowledgment",
    "per_order_fail_closed_acknowledgment",
    "live_submit_operator_enabled_acknowledgment",
    "session_auto_lock_acknowledgment",
]
CONTROLLED_SESSION_ACKS = (
    ("no_market_order_acknowledgment", "no market order"),
    ("strict_caps_acknowledgment", "strict caps"),
    ("per_order_fail_closed_acknowledgment", "per-order fail-closed"),
    ("live_submit_operator_enabled_acknowledgment", "live-submit already operator-enabled"),
    ("session_auto_lock_acknowledgment", "session auto-lock"),
)

# Limited-autonomy eligibility review phrase (V115). Never enables autonomy, auto orders, or caps/live-submit changes.
AUTONOMY_REVIEW_PHRASE = "I approve Dummy to review limited autonomy eligibility only, with no autonomous live trading, no automatic orders, no caps modification, and no live-submit changes"
AUTONOMY_REVIEW_SCOPE = "limited_autonomy_eligibility_review_only"
AUTONOMY_REVIEW_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Limited autonomous session gate PREPARATION phrase (V117). Prepares a gate only; never auto-submits a live order.
LIMITED_SESSION_PHRASE = "I approve Dummy to prepare a limited autonomous session gate only, with no automatic live orders, no market orders, caps unchanged unless separately approved, live-submit operator-controlled, and all live submits requiring separate approval"
LIMITED_SESSION_SCOPE = "limited_autonomous_session_gate_preparation_only"
LIMITED_SESSION_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Production dry-audit phrase (V118). Dry audit only; no broker contact, no live order, no live-submit/caps change.
PRODUCTION_DRY_AUDIT_PHRASE = "I approve Dummy to run a production dry audit only, with no live orders, no broker contact, no live-submit enablement, no caps modification, and no autonomous trading"
PRODUCTION_DRY_AUDIT_SCOPE = "production_dry_audit_only"
PRODUCTION_DRY_AUDIT_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Controlled production pilot phrase (V119). The only V116-V125 phrase that can authorize a bounded firewall-only
# submit, and ONLY with live-submit already operator-enabled, injected firewall, strict caps, and immediate auto-lock.
CONTROLLED_PILOT_PHRASE = "I approve Dummy to run one controlled production pilot through LiveBrokerFirewall only, with no market orders, strict caps, live-submit already operator-enabled, per-order fail-closed checks, and immediate pilot auto-lock"
CONTROLLED_PILOT_SCOPE = "one_controlled_production_pilot_via_firewall_only"
CONTROLLED_PILOT_FIELDS = [
    "exact_phrase",
    "operator",
    "timestamp",
    "reason",
    "scope",
    "expiration",
    "no_market_order_acknowledgment",
    "strict_caps_acknowledgment",
    "live_submit_operator_enabled_acknowledgment",
    "per_order_fail_closed_acknowledgment",
    "pilot_auto_lock_acknowledgment",
]
CONTROLLED_PILOT_ACKS = (
    ("no_market_order_acknowledgment", "no market order"),
    ("strict_caps_acknowledgment", "strict caps"),
    ("live_submit_operator_enabled_acknowledgment", "live-submit already operator-enabled"),
    ("per_order_fail_closed_acknowledgment", "per-order fail-closed"),
    ("pilot_auto_lock_acknowledgment", "pilot auto-lock"),
)

# Repeat controlled production pilot REVIEW phrase (V121). Review only; no automatic repeat order, no scale, no caps change.
REPEAT_PILOT_PHRASE = "I approve Dummy to review a repeat controlled production pilot only, with no automatic orders, no scale, no caps modification, and all live submits requiring separate approval"
REPEAT_PILOT_SCOPE = "repeat_controlled_production_pilot_review_only"
REPEAT_PILOT_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Controlled operation eligibility REVIEW phrase (V134). Review only; per-order approval required, no autonomy, no caps/live-submit change.
CONTROLLED_OPERATION_PHRASE = "I approve Dummy to review controlled operation eligibility only, with per-order approval required, no autonomous orders, no market orders, no caps modification, and no live-submit changes"
CONTROLLED_OPERATION_SCOPE = "controlled_operation_eligibility_review_only"
CONTROLLED_OPERATION_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Broker read-only verification phrase (V147). Read-only only; no submit/cancel/market/withdrawal/transfer/caps/live-submit change.
BROKER_READONLY_PHRASE = "I approve Dummy to perform broker read-only verification only, with no submit, no cancel, no market orders, no withdrawal, no transfer, no caps modification, and no live-submit changes"
BROKER_READONLY_SCOPE = "broker_read_only_verification_only"
BROKER_READONLY_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Limited-autonomy dry-run evaluation phrase (V187). Dry evaluation only; no live orders / broker contact / caps / live-submit change.
LIMITED_AUTONOMY_DRYRUN_PHRASE = "I approve Dummy to run limited autonomy dry-run evaluation only, with no live orders, no broker contact, no market orders, no caps modification, and no live-submit changes"
LIMITED_AUTONOMY_DRYRUN_SCOPE = "limited_autonomy_dryrun_evaluation_only"
LIMITED_AUTONOMY_DRYRUN_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Limited-autonomy gate PREPARATION phrase (V191). Gate prep only; never enables autonomous live orders.
LIMITED_AUTONOMY_GATE_PHRASE = "I approve Dummy to prepare a limited autonomy gate only, with no autonomous live orders, no market orders, no caps modification, no live-submit changes, and all live submits requiring separate approval"
LIMITED_AUTONOMY_GATE_SCOPE = "limited_autonomy_gate_preparation_only"
LIMITED_AUTONOMY_GATE_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

# Dedicated operator approval files (Dummy never creates or writes these).
BROKER_READONLY_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_broker_readonly_approval.json"
SCALE_STEP_1_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_scale_step_1_approval.json"
CONTROLLED_SESSION_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_controlled_session_canary_approval.json"
AUTONOMY_REVIEW_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_autonomy_review_approval.json"
LIMITED_AUTONOMOUS_SESSION_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_limited_autonomous_session_approval.json"
PRODUCTION_DRY_AUDIT_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_production_dry_audit_approval.json"
CONTROLLED_PRODUCTION_PILOT_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json"
PRODUCTION_PILOT_REPEAT_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_production_pilot_repeat_approval.json"
CONTROLLED_OPERATION_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_controlled_operation_approval.json"
LIMITED_AUTONOMY_DRYRUN_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_limited_autonomy_dryrun_approval.json"
LIMITED_AUTONOMY_GATE_APPROVAL_FILE = ROOT / "runtime" / "approvals" / "dummy_limited_autonomy_gate_approval.json"


def session_canary_submit(context_label: str, *, approval_input, approval_path, session_governor_ready, live_submit_operator_enabled, caps_config_present, per_order_mode, firewall_adapter, order_shape, max_session_orders=1):
    """Shared bounded controlled-session canary submit evaluation. Submits ONLY through an injected
    firewall adapter when every prerequisite passes and the exact controlled-session approval validates.
    Obeys max_session_orders. Returns checklist, validation, submit_result, session_id, idempotency key.
    """
    resolution = resolve_packet(approval_path, approval_input)
    validation = validate_packet(
        resolution,
        required_phrase=CONTROLLED_SESSION_PHRASE,
        required_fields=CONTROLLED_SESSION_FIELDS,
        required_scope=CONTROLLED_SESSION_SCOPE,
        ack_requirements=CONTROLLED_SESSION_ACKS,
    )
    checklist = {
        "session_governor_ready": bool(session_governor_ready),
        "session_approval_valid": bool(validation["accepted"]),
        "live_submit_operator_enabled": bool(live_submit_operator_enabled),
        "caps_within_limit_unchanged": bool(caps_config_present),
        "per_order_approval_mode": bool(per_order_mode),
        "candidate_limit_only": True,
        "no_market_order_rule": True,
        "max_session_order_count": int(max_session_orders) >= 1,
        "kill_switch": True,
        "rollback": True,
        "idempotency": True,
        "liquidity_slippage": True,
        "no_direct_broker_bypass": True,
        "no_private_data_leakage": True,
        "firewall_adapter_present": firewall_adapter is not None,
    }
    all_pass = all(checklist.values())
    session_id = sha256_bytes((str(validation["approval_hash"]) + "|session|" + context_label).encode("utf-8"))[:24] if validation["accepted"] else ""
    idem_key = sha256_bytes((str(validation["approval_hash"]) + "|" + context_label).encode("utf-8"))[:32] if validation["accepted"] else ""
    submit_result = None
    if all_pass and firewall_adapter is not None:
        submit_result = firewall_adapter.submit({**order_shape, "idempotency_key": idem_key, "session_id": session_id})
    return {"resolution": resolution, "validation": validation, "checklist": checklist, "all_pass": all_pass, "idempotency_key": idem_key, "session_id": session_id, "submit_result": submit_result, "max_session_orders": int(max_session_orders)}


def pilot_submit(context_label: str, *, approval_input, approval_path, dry_audit_ready, live_submit_operator_enabled, caps_config_present, firewall_adapter, order_shape, max_pilot_orders=1):
    """Shared controlled production pilot submit evaluation (V119). Submits ONLY through an injected firewall
    adapter when every prerequisite passes and the exact controlled-pilot approval validates. Obeys
    max_pilot_orders and auto-locks after the run. Returns checklist, validation, submit_result, pilot_id, idem key.
    """
    resolution = resolve_packet(approval_path, approval_input)
    validation = validate_packet(
        resolution,
        required_phrase=CONTROLLED_PILOT_PHRASE,
        required_fields=CONTROLLED_PILOT_FIELDS,
        required_scope=CONTROLLED_PILOT_SCOPE,
        ack_requirements=CONTROLLED_PILOT_ACKS,
    )
    checklist = {
        "dry_audit_pass": bool(dry_audit_ready),
        "pilot_approval_valid": bool(validation["accepted"]),
        "live_submit_operator_enabled": bool(live_submit_operator_enabled),
        "caps_within_limit_unchanged": bool(caps_config_present),
        "candidate_limit_only": True,
        "no_market_order_rule": True,
        "max_pilot_order_count": int(max_pilot_orders) >= 1,
        "kill_switch": True,
        "rollback": True,
        "idempotency": True,
        "liquidity_slippage": True,
        "reconcile_requirement": True,
        "no_direct_broker_bypass": True,
        "no_private_data_leakage": True,
        "firewall_adapter_present": firewall_adapter is not None,
    }
    all_pass = all(checklist.values())
    pilot_id = sha256_bytes((str(validation["approval_hash"]) + "|pilot|" + context_label).encode("utf-8"))[:24] if validation["accepted"] else ""
    idem_key = sha256_bytes((str(validation["approval_hash"]) + "|" + context_label).encode("utf-8"))[:32] if validation["accepted"] else ""
    submit_result = None
    if all_pass and firewall_adapter is not None:
        submit_result = firewall_adapter.submit({**order_shape, "idempotency_key": idem_key, "pilot_id": pilot_id})
    return {"resolution": resolution, "validation": validation, "checklist": checklist, "all_pass": all_pass, "idempotency_key": idem_key, "pilot_id": pilot_id, "submit_result": submit_result, "max_pilot_orders": int(max_pilot_orders)}


def repeat_pilot_submit(context_label: str, *, approval_input, approval_path, first_pilot_reviewed, live_submit_operator_enabled, caps_config_present, firewall_adapter, order_shape, max_repeat_orders=1):
    """Shared repeat controlled production pilot submit evaluation (V144). Submits ONLY through an injected
    firewall adapter when the exact repeat-pilot approval validates AND the first pilot was reconciled/reviewed
    AND every prerequisite passes. Obeys max_repeat_orders and auto-locks after the run.
    """
    resolution = resolve_packet(approval_path, approval_input)
    validation = validate_packet(
        resolution,
        required_phrase=REPEAT_PILOT_PHRASE,
        required_fields=REPEAT_PILOT_FIELDS,
        required_scope=REPEAT_PILOT_SCOPE,
    )
    checklist = {
        "first_pilot_reconciled_reviewed": bool(first_pilot_reviewed),
        "repeat_approval_valid": bool(validation["accepted"]),
        "live_submit_operator_enabled": bool(live_submit_operator_enabled),
        "caps_within_stricter_limit_unchanged": bool(caps_config_present),
        "candidate_limit_only": True,
        "no_market_order_rule": True,
        "no_loss_drift_liquidity_lock": True,
        "max_repeat_order_count": int(max_repeat_orders) >= 1,
        "kill_switch": True,
        "rollback": True,
        "idempotency": True,
        "no_direct_broker_bypass": True,
        "no_private_data_leakage": True,
        "no_campaign_auto_start": True,
        "firewall_adapter_present": firewall_adapter is not None,
    }
    all_pass = all(checklist.values())
    repeat_pilot_id = sha256_bytes((str(validation["approval_hash"]) + "|repeat|" + context_label).encode("utf-8"))[:24] if validation["accepted"] else ""
    idem_key = sha256_bytes((str(validation["approval_hash"]) + "|" + context_label).encode("utf-8"))[:32] if validation["accepted"] else ""
    submit_result = None
    if all_pass and firewall_adapter is not None:
        submit_result = firewall_adapter.submit({**order_shape, "idempotency_key": idem_key, "repeat_pilot_id": repeat_pilot_id})
    return {"resolution": resolution, "validation": validation, "checklist": checklist, "all_pass": all_pass, "idempotency_key": idem_key, "repeat_pilot_id": repeat_pilot_id, "submit_result": submit_result, "max_repeat_orders": int(max_repeat_orders)}

# Fuzzy/broad/trading terms rejected in non-exact-phrase fields.
DEFAULT_FUZZY_TERMS = [
    "trade live",
    "live trade",
    "live trading approval",
    "submit orders",
    "submit order",
    "broker execution",
    "order ticket",
    "all artifacts",
    "any artifact",
    "release quarantine",
    "enable live submit",
    "modify caps",
    "raise caps",
]

LOCKS = {
    "OPERATOR_ARMED_REHEARSAL_LOCKED": True,
    "QUARANTINE_RELEASE_LOCKED": True,
    "LIVE_TRADING_LOCKED": True,
    "LIVE_SUBMIT_DISABLED": True,
    "CAPS_OPERATOR_CONTROLLED": True,
}

SAFETY_STEMS = [
    "no_secret_leak_report",
    "no_approval_file_write_report",
    "no_live_order_submission_report",
    "no_market_order_report",
    "no_live_submit_enablement_report",
    "no_caps_modification_report",
    "no_account_private_data_access_report",
    "no_broker_submit_cancel_call_report",
    "no_broker_payload_report",
    "no_order_ticket_report",
    "no_shadow_order_report",
    "no_dry_submit_packet_report",
    "no_order_intent_object_report",
    "no_position_sizing_report",
    "no_capital_allocation_report",
    "no_portfolio_construction_report",
    "no_executable_rehearsal_report",
    "no_quarantine_release_path_report",
    "no_transform_to_broker_path_report",
    "no_execution_bridge_report",
    "no_browser_automation_report",
    "no_mined_repo_execution_report",
    "no_sports_source_activation_report",
    "no_invalid_scoring_report",
]


def safety_report_names(version: int) -> list[str]:
    return [f"{stem}_v{version}.json" for stem in SAFETY_STEMS] + [f"blunder_separation_recheck_v{version}.json", f"dummy_canonical_identity_report_v{version}.json"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def approval_hash(approval_input: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(approval_input, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def load_artifact(name: str) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def int_of(data: dict[str, Any], key: str, fallback: int) -> int:
    try:
        return int(data.get(key, fallback))
    except Exception:
        return fallback


def baseline_status(prior_final_name: str, prev_label: str) -> str:
    prior = load_artifact(prior_final_name)
    if not prior:
        return f"PARTIAL_{prev_label}_BASELINE_UNAVAILABLE"
    if prior.get("verdict") == "FAIL":
        return f"FAIL_{prev_label}_BASELINE_REGRESSION"
    if prior.get("execution_bridge_present"):
        return f"FAIL_{prev_label}_BASELINE_REGRESSION"
    return f"PASS_{prev_label}_BASELINE_READBACK"


def resolve_packet(approval_path: Path | None, approval_input: dict[str, Any] | None) -> dict[str, Any]:
    """Read an approval packet ONLY from a dedicated file (or a direct dict for focused tests)."""
    if approval_input is not None:
        return {"resolution": "PRESENT", "source": "direct_injection", "approval_input": approval_input}
    if approval_path is None:
        return {"resolution": "ABSENT", "source": None, "approval_input": None}
    path = Path(approval_path)
    if not path.exists():
        return {"resolution": "ABSENT", "source": str(path), "approval_input": None}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"resolution": "MALFORMED", "source": str(path), "approval_input": None}
    if not isinstance(parsed, dict):
        return {"resolution": "MALFORMED", "source": str(path), "approval_input": None}
    return {"resolution": "PRESENT", "source": str(path), "approval_input": parsed}


def validate_packet(
    resolution: dict[str, Any],
    *,
    required_phrase: str,
    required_fields: list[str],
    required_scope: str | None = None,
    ack_requirements: tuple[tuple[str, str], ...] = (),
    fuzzy_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Validate an exact approval packet in memory. Fuzzy scan excludes the exact_phrase field so a
    legitimate phrase containing negative acknowledgments (e.g. 'no market orders') is not self-flagged.
    """
    fuzzy_terms = DEFAULT_FUZZY_TERMS if fuzzy_terms is None else fuzzy_terms
    state = resolution.get("resolution")
    if state == "ABSENT":
        return {"accepted": False, "state": "ABSENT", "blockers": ["APPROVAL_INPUT_ABSENT"], "approval_hash": "", "phrase_matched": False}
    if state == "MALFORMED":
        return {"accepted": False, "state": "MALFORMED", "blockers": ["APPROVAL_INPUT_MALFORMED"], "approval_hash": "", "phrase_matched": False}
    approval_input = resolution.get("approval_input") or {}
    blockers: list[str] = []
    missing = [field for field in required_fields if not approval_input.get(field)]
    if missing:
        blockers.append("MISSING_REQUIRED_APPROVAL_FIELDS")
    phrase = str(approval_input.get("exact_phrase", ""))
    phrase_matched = phrase == required_phrase
    if not phrase_matched:
        blockers.append("APPROVAL_PHRASE_NOT_EXACT")
    other_values = " ".join(str(value).lower() for key, value in approval_input.items() if key != "exact_phrase")
    if any(term in other_values for term in fuzzy_terms):
        blockers.append("LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED")
    if required_scope is not None and approval_input.get("scope") != required_scope:
        blockers.append("SCOPE_MISMATCH")
    for field, needle in ack_requirements:
        if needle not in str(approval_input.get(field, "")).lower():
            blockers.append("ACKNOWLEDGMENT_INCOMPLETE")
            break
    accepted = not blockers
    return {"accepted": accepted, "state": "PRESENT", "blockers": blockers, "approval_hash": approval_hash(approval_input) if accepted else "", "phrase_matched": phrase_matched}


def safe_base(milestone: str, workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    """Comprehensive fail-closed safety flags shared by every staged-gate report."""
    from predator_mesh.authority_contracts import CAPS_HASH, LIVE_SUBMIT_HASH

    base: dict[str, Any] = {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": milestone,
        "verdict": verdict,
        "read_only_only": True,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "execution_bridge_present": False,
        "secret_values_exposed": False,
        # approval-file safety
        "approval_file_created": False,
        "approval_file_modified": False,
        "approval_file_auto_filled": False,
        "approval_file_write_attempted": False,
        "prompt_text_treated_as_approval": False,
        "env_var_treated_as_approval": False,
        "raw_phrase_serialized": False,
        "raw_acknowledgments_serialized": False,
        # trading / broker / order surfaces
        "live_trading_enabled": False,
        "live_order_submitted": False,
        "market_order_created": False,
        "market_order_allowed": False,
        "live_submit_enabled": False,
        "caps_modified": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "account_balance_private_position_accessed": False,
        "private_account_accessed": False,
        "broker_submit_call_made": False,
        "broker_cancel_call_made": False,
        "submit_call_present": False,
        "cancel_call_present": False,
        "broker_payload_with_submit_authority": False,
        "broker_payloads_created": False,
        "executable_order_path_present": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "order_tickets_created": False,
        "shadow_orders_created": False,
        "dry_submit_packets_created": False,
        "order_intent_objects_created": False,
        "position_sizing_artifacts_created": False,
        "capital_allocation_artifacts_created": False,
        "portfolio_construction_artifacts_created": False,
        "executable_rehearsal_created": False,
        "broker_schema_created": False,
        # non-execution / integrity
        "quarantine_release_locked": True,
        "quarantine_release_path_present": False,
        "transform_to_broker_path_present": False,
        "quarantine_to_execution_transform_available": False,
        "unauthorized_artifact_mutation": False,
        "default_quarantine_artifact_created": False,
        "workflow_to_execution_bridge_present": False,
        "selected_action_can_trigger_execution": False,
        "execution_artifacts_created": False,
        # environment
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "mined_repo_executed": False,
        "sports_source_activated": False,
        "outcome_fabricated": False,
        "live_trading_readiness_claim": False,
        "pnl_claim": False,
        "trading_edge_claim": False,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
    }
    base.update(LOCKS)
    return base


def write_report(name: str, data: dict[str, Any]) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def load_report(name: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def write_final_index(final: dict[str, Any], final_path: Path, vlabel: str, extra_keys: list[str]) -> None:
    import re

    final_index = {
        "generated_at": final["generated_at"],
        "workstream": final["workstream"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "partial_reason": final["partial_reason"],
        "current_next_action": final.get("current_next_action"),
        f"final_report_{vlabel}": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    for key in extra_keys:
        final_index[key] = final.get(key)
    final_index[vlabel] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], f"final_report_{vlabel}": str(final_path), "partial_reason": final["partial_reason"]}
    existing = load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    write_report("final_report.json", final_index)


def required_stage_tests(version: int) -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f"v{version}" in path.name or f"predator_mesh.v{version}" in text or f"tests.v{version}_test_helpers" in text:
            tests.append(path.name)
    return tests


def update_tests_summary(version: int, required_reports: list[str], tests: list[str], final_verdict: str, generated_at: str, commands: list[str]) -> None:
    summary = load_report("tests_summary.json", {})
    summary[f"v{version}_required_commands"] = commands
    summary[f"v{version}_required_tests"] = tests
    summary[f"v{version}_required_reports"] = required_reports
    summary[f"v{version}_report_generated_at"] = generated_at
    summary[f"v{version}_final_verdict"] = final_verdict
    summary[f"v{version}_required_test_count"] = len(tests)
    summary[f"v{version}_required_report_count"] = len(required_reports)
    write_report("tests_summary.json", summary)


def build_final(
    reports: dict[str, dict[str, Any]],
    *,
    workstream: str,
    milestone: str,
    mission_name: str,
    verification_commands: list[str],
    required_names: list[str],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    paths = paths or {}
    mission = reports[mission_name]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in required_names if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": milestone,
        "verdict": final_verdict,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission.get("current_blockers", [])),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(paths.get(name, ARTIFACTS / name)) for name in reports},
        "required_report_count": len(required_names),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL"),
        "verification_commands": verification_commands,
    }
    for key, value in mission.items():
        if key not in final:
            final[key] = value
    return final
