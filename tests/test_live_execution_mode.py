"""Tests for the shared live execution mode classifier."""

from __future__ import annotations

from core.live_execution_mode import LIVE_PROOF_ENV_ACK, LiveExecutionMode, classify_live_execution_mode


def _base_context(overrides: dict | None = None) -> dict:
    ctx = {
        "live_submit_config": {"enabled": False},
        "env": {},
        "seal_status": "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT",
        "caps_strict": True,
        "descriptor_staged": True,
        "credentials_ready": True,
        "proof_lock_clear": True,
    }
    if overrides:
        ctx.update(overrides)
    return ctx


def test_default_disabled():
    mode, blocker, ctx = classify_live_execution_mode(
        **_base_context({"live_submit_config": {"enabled": False}})
    )
    assert mode is LiveExecutionMode.DEFAULT_DISABLED
    assert blocker == "DEFAULT_DISABLED"
    assert ctx["env_mode"] is False


def test_invalid_live_submit_config():
    mode, blocker, ctx = classify_live_execution_mode(
        **_base_context({"live_submit_config": {"enabled": True, "proof_scope": "wrong"}})
    )
    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == "LIVE_SUBMIT_INVALID"
    assert "errors" in ctx


def test_missing_env_gate():
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    mode, blocker, _ = classify_live_execution_mode(
        **_base_context({"live_submit_config": cfg})
    )
    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == "ENV_GATE_MISSING"


def test_command_seal_not_ready():
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    env = {
        "DUMMY_LIVE_PROOF_MODE": "1",
        "DUMMY_LIVE_PROOF_ACK": LIVE_PROOF_ENV_ACK,
    }
    mode, blocker, _ = classify_live_execution_mode(
        **_base_context(
            {
                "live_submit_config": cfg,
                "env": env,
                "seal_status": "PARTIAL_COMMAND_SEAL_BLOCKED",
            }
        )
    )
    assert mode is LiveExecutionMode.INVALID_OR_BLOCKED
    assert blocker == "COMMAND_SEAL_NOT_READY"


def test_one_proof_live_ready():
    cfg = {
        "enabled": True,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "operator": "chris",
        "reason": "test",
        "timestamp": "2026-01-01T00:00:00Z",
        "expiry": "2099-01-01T00:00:00Z",
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    env = {
        "DUMMY_LIVE_PROOF_MODE": "1",
        "DUMMY_LIVE_PROOF_ACK": LIVE_PROOF_ENV_ACK,
    }
    mode, blocker, ctx = classify_live_execution_mode(
        **_base_context({"live_submit_config": cfg, "env": env})
    )
    assert mode is LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY
    assert blocker == ""
    assert ctx["env_mode"] is True
    assert ctx["env_ack"] is True
