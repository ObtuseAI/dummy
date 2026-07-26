"""DUMMY v298 execute-once final proof runner V7 (full-authority only) — default not armed/no submit; real broker submit only when all gates pass."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.env_loader import kalshi_credential_status
from core.ontology import LiveOrderResult
from core.proof_lock import proof_lock_clear as _proof_lock_clear
from predator_mesh import final_console_common as fcc
from predator_mesh.brokers import LimitOrderRequest
MILESTONE = "DUMMY_V298_EXECUTE_ONCE_FINAL_PROOF_RUNNER_V7_FULL_AUTH_ONLY_V1"

ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
CAPS_PATH = Path("configs/caps.json")
LIVE_SUBMIT_PATH = Path("configs/live_submit.json")


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _kalshi_credentials_ready() -> bool:
    """Return True if a Kalshi key id and private-key ref are present."""
    status = kalshi_credential_status()
    if not status.get("KALSHI_API_KEY_ID", {}).get("present"):
        return False
    key_refs = {
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    }
    for key in key_refs:
        entry = status.get(key, {})
        if not entry.get("present"):
            continue
        if "file_exists" in entry:
            if entry["file_exists"]:
                return True
        else:
            return True
    return False


def _load_live_submit_config() -> dict[str, Any]:
    if not LIVE_SUBMIT_PATH.exists():
        return {"enabled": False}
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def _caps_strict() -> bool:
    if not CAPS_PATH.exists():
        return False
    try:
        data = json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _descriptor_staged() -> bool:
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return False
    try:
        data = json.loads(ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("broker") == "KALSHI"
        and data.get("adapter_type") == "LiveBrokerFirewall"
        and data.get("order_type_policy") == "LIMIT_ONLY"
        and data.get("market_orders_allowed") is False
    )


def _command_seal_ready() -> bool:
    v297 = Path("artifacts/dummy/final_report_v297.json")
    if not v297.exists():
        return False
    try:
        data = json.loads(v297.read_text(encoding="utf-8"))
    except Exception:
        return False
    return str(data.get("execute_once_command_seal_controller_status", "")) == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"


def _idempotency_key(proof_id: str, nonce: str) -> str:
    descriptor_hash = _sha256_file(ADAPTER_DESCRIPTOR_PATH) or ""
    caps_hash = _sha256_file(CAPS_PATH) or ""
    live_submit_hash = _sha256_file(LIVE_SUBMIT_PATH) or ""
    payload = f"{proof_id}|{descriptor_hash}|{caps_hash}|{live_submit_hash}|{nonce}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _build_limit_order_request(proof_id: str, market_ticker: str, nonce: str) -> LimitOrderRequest:
    idem = _idempotency_key(proof_id, nonce)
    return LimitOrderRequest(
        venue="KALSHI",
        order_type="LIMIT",
        market_orders_allowed=False,
        side="yes",
        action="buy",
        price=1,
        quantity=1,
        idempotency_key=idem,
        market_ticker=market_ticker,
        proof_id=proof_id,
        proof_target="FIRST_REAL_PILOT_PROOF",
        client_order_id=idem,
        max_order_count=1,
        max_order_size_cents=100,
    )


WORKSTREAM = "v298: Execute-Once Final Proof Runner V7 Full-Auth Only"
DASH_TITLE = "Dummy V298 Execute-Once Final Proof Runner V7"
MISSION_KEY = "dummy_mission_state_report_v298"
CONTROLLER_KEY = "execute_once_final_proof_runner_v7_controller_status"

ARM_CHECKS = [
    ("command_seal_ready", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_COMMAND_SEAL"),
    ("env_mode", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_ENV_GATE"),
    ("env_ack", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_ENV_GATE"),
    ("live_authorized", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("resolver_armable", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("approval_exact", "FAIL_CLOSED_EXECUTE_ONCE_FINAL_PROOF_RUNNER_APPROVAL_INVALID"),
    ("live_submit_enabled", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("caps_confirmed", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("adapter_injected", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_ADAPTER"),
    ("proof_target_valid", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("limit_only", "FAIL_CLOSED_EXECUTE_ONCE_FINAL_PROOF_RUNNER_MARKET_ORDER_REJECTED"),
    ("idempotency_key", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY"),
    ("proof_lock_clear", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_STALE_PROOF_LOCK"),
    ("not_repeat", "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_REPEAT_AUTO_LOCKED"),
]

REPORT_GROUPS: dict[str, list[str]] = {
    "execute-once-final-proof-runner-v7": ["v298_execute_once_final_proof_runner_v7_controller_report.json"],
    "v297-baseline": ["v297_baseline_readback_v1_report.json"],
    "arm-requirements": ["v298_arm_requirements_report.json"],
    "no-fixture-inflation-proof": ["v298_no_fixture_inflation_proof_report.json"],
    "no-submit-proof": ["v298_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v298_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v258_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v257_report.json"],
    "mission-state": ["dummy_mission_state_report_v298.json", "dashboard_v298_report_v1.json", "completion_oriented_next_action_v298_report.json"],
}

V298_ROUTES = [f"/api/v298/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Runner", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, arm: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    if not arm:
        return {
            "status": "PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED",
            "verdict": "PARTIAL",
            "fields": {
                "arm_state": "NOT_ARMED_DRY_DEFAULT",
                "fixture_only": False,
                "uses_non_broker_double": False,
                "non_broker_double_used": False,
                "fixture_proof_inflates_real_score": False,
                "real_live_orders_submitted": 0,
                "real_live_orders_submitted_count": 0,
                "real_broker_contacted": False,
                "broker_rejection_captured": False,
                "market_order_submitted": False,
                "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
                "no_submit_proof_status": "PASS_NO_SUBMIT",
                "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
            },
            "blockers": ["EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED_DRY_DEFAULT"],
            "next_action": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED_NEXT_SEAL_COMMAND_THEN_OPERATOR_FULL_AUTHORITY_NO_SUBMIT_BY_DUMMY",
        }
    for key, block_status in ARM_CHECKS:
        if not arm.get(key):
            return {
                "status": block_status,
                "verdict": "PARTIAL",
                "fields": {
                    "arm_state": "BLOCKED",
                    "block_requirement": key,
                    "fixture_only": True,
                    "uses_non_broker_double": False,
                    "non_broker_double_used": False,
                    "fixture_proof_inflates_real_score": False,
                    "real_live_orders_submitted": 0,
                    "real_live_orders_submitted_count": 0,
                    "real_broker_contacted": False,
                    "broker_rejection_captured": False,
                    "market_order_submitted": False,
                    "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
                    "no_submit_proof_status": "PASS_NO_SUBMIT",
                    "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
                },
                "blockers": [block_status],
                "next_action": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_" + key.upper() + "_NO_SUBMIT_BY_DUMMY",
            }
    # Armed: decide whether this is a real one-proof live attempt or a rehearsal/test double.
    from core.live_execution_mode import classify_live_execution_mode, LiveExecutionMode

    mode, blocker, _ = classify_live_execution_mode(
        live_submit_config=_load_live_submit_config(),
        env=dict(os.environ),
        seal_status=("PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT" if _command_seal_ready() else "BLOCKED"),
        caps_strict=_caps_strict(),
        descriptor_staged=_descriptor_staged(),
        credentials_ready=_kalshi_credentials_ready(),
        proof_lock_clear=_proof_lock_clear(),
    )

    if mode is not LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY:
        # Rehearsal / test double path: preserve the legacy non-broker-double report shape.
        return {
            "status": "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED",
            "verdict": "PASS",
            "fields": {
                "arm_state": "SUBMITTED_AUTOLOCKED_NON_BROKER_DOUBLE",
                "fixture_only": True,
                "uses_non_broker_double": True,
                "non_broker_double_used": True,
                "submitted_autolocked": True,
                "real_live_orders": 0,
                "real_live_orders_submitted_count": 0,
                "real_broker_contacted": False,
                "broker_rejection_captured": False,
                "market_order_submitted": False,
                "max_attempts": 1,
                "fixture_proof_inflates_real_score": False,
                "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
                "no_submit_proof_status": "PASS_NO_SUBMIT",
                "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
                "proof_is_real": False,
            },
            "blockers": [],
            "next_action": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED_FIXTURE_ONLY_NEXT_RUN_POST_PROOF_AUTO_INTAKE_NO_NEW_ORDER",
        }

    # Real one-proof live attempt.
    proof_id = f"v298-{MILESTONE}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    market_ticker = "KXBTC-26DEC25000-C"  # smallest-proof conservative default
    req = _build_limit_order_request(proof_id, market_ticker, nonce=proof_id)

    result = LiveOrderResult(
        success=False,
        error="LEGACY_V298_RUNNER_RETIRED_USE_CENTRAL_FIREWALL",
        proof_reference=proof_id,
        broker_contacted=False,
    )

    real_broker_contacted = bool(result.broker_contacted)
    real_live_orders_submitted_count = 1 if (result.success and result.order_id) else 0
    broker_rejection_captured = bool(not result.success and real_broker_contacted)
    broker_order_id = result.order_id if result.success else None
    broker_rejection_reason = result.error if broker_rejection_captured else None
    proof_is_real = real_broker_contacted

    # Structured broker-rejection diagnostics (legacy-safe fallback).
    broker_rejection_code = getattr(result, "broker_rejection_code", None)
    broker_rejection_safe_message = getattr(result, "broker_rejection_safe_message", None)
    broker_rejection_http_status = getattr(result, "broker_rejection_http_status", None)
    broker_rejection_adapter_error_type = getattr(result, "broker_rejection_adapter_error_type", None)
    broker_rejection_stage = getattr(result, "broker_rejection_stage", None)
    broker_rejection_raw_redacted = getattr(result, "broker_rejection_raw_redacted", None)
    if broker_rejection_code is None and broker_rejection_captured:
        broker_rejection_code = result.error

    return {
        "status": "PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_RETIRED_CENTRAL_FIREWALL_REQUIRED",
        "verdict": "PARTIAL",
        "fields": {
            "arm_state": "BLOCKED_LEGACY_RUNNER_RETIRED",
            "fixture_only": False,
            "uses_non_broker_double": False,
            "non_broker_double_used": False,
            "submitted_autolocked": False,
            "real_live_orders": real_live_orders_submitted_count,
            "real_live_orders_submitted_count": real_live_orders_submitted_count,
            "real_broker_contacted": real_broker_contacted,
            "broker_rejection_captured": broker_rejection_captured,
            "broker_order_id": broker_order_id,
            "broker_rejection_reason": broker_rejection_reason,
            "broker_rejection_code": broker_rejection_code,
            "broker_rejection_safe_message": broker_rejection_safe_message,
            "broker_rejection_http_status": broker_rejection_http_status,
            "broker_rejection_adapter_error_type": broker_rejection_adapter_error_type,
            "broker_rejection_stage": broker_rejection_stage,
            "broker_rejection_raw_redacted": broker_rejection_raw_redacted,
            "market_order_submitted": False,
            "max_attempts": 1,
            "fixture_proof_inflates_real_score": False,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT" if real_live_orders_submitted_count == 0 else "PASS_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT" if not real_broker_contacted else "PASS_BROKER_CONTACT",
            "proof_is_real": proof_is_real,
            "idempotency_key": req.idempotency_key,
            "proof_id": proof_id,
            "market_ticker": market_ticker,
        },
        "blockers": ["LEGACY_V298_RUNNER_RETIRED_USE_CENTRAL_FIREWALL"],
        "next_action": "ROUTE_ANY_SEPARATELY_AUTHORIZED_PROPOSAL_THROUGH_CENTRAL_FIREWALL_NO_LEGACY_SUBMIT",
    }


_BUNDLE = fcc.StageBundle(
    version=298, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V298_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/operator_proof_stages/execute_once.py predator_mesh/operator_proof_workflows.py scripts/run_dummy_execute_once_final_proof_v7.py",
    "python scripts/run_dummy_execute_once_final_proof_v7.py",
    "python -m pytest tests/test_v298_real_proof_semantics.py tests/test_execute_once_real_broker_wiring.py tests/test_proof_lock_after_broker_rejection.py -q",
]


def full_authority_arm() -> dict[str, Any]:
    """Fixture full-authority arm packet (all checks met). Non-broker double downstream; tests only."""
    return {k: True for k, _ in ARM_CHECKS} | {"env_mode": True, "env_ack": True}


class ExecuteOnceProofReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
