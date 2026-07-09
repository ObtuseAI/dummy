"""Tests for the shared live-submit state model.

These tests validate both the default disabled state and the explicit
operator-approved one-proof enabled state. They never load real secrets,
never contact a broker, and never mutate repo config.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from core.live_submit_state import (
    LIVE_SUBMIT_REQUIRED_ACK,
    LIVE_SUBMIT_TYPED_CONFIRMATION,
    LiveSubmitState,
    classify_live_submit_state,
    load_live_submit_config,
    validate_default_disabled,
    validate_operator_one_proof_enabled,
)


def _future_expiry(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_one_proof_config(**overrides):
    config = {
        "enabled": True,
        "operator": "chris",
        "reason": "one controlled proof",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": _future_expiry(),
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Default disabled state
# ---------------------------------------------------------------------------


def test_load_default_config_from_repo_is_disabled_or_intentionally_enabled():
    """Repo live-submit config is loadable and matches one of the two valid states."""
    from core.live_submit_state import classify_live_submit_state

    config = load_live_submit_config()
    state = classify_live_submit_state(config)
    assert state in (
        LiveSubmitState.DEFAULT_DISABLED_VALID,
        LiveSubmitState.OPERATOR_ONE_PROOF_ENABLED_VALID,
    )


def test_validate_default_disabled_accepts_explicit_false():
    result = validate_default_disabled({"enabled": False})
    assert result.ok is True
    assert result.state is LiveSubmitState.DEFAULT_DISABLED_VALID


def test_validate_default_disabled_accepts_missing_enabled():
    result = validate_default_disabled({})
    assert result.ok is True
    assert result.state is LiveSubmitState.DEFAULT_DISABLED_VALID


def test_validate_default_disabled_rejects_enabled_true():
    result = validate_default_disabled({"enabled": True})
    assert result.ok is False
    assert result.state is LiveSubmitState.INVALID


def test_classify_default_state():
    state = classify_live_submit_state({"enabled": False})
    assert state is LiveSubmitState.DEFAULT_DISABLED_VALID


# ---------------------------------------------------------------------------
# Operator one-proof enabled state
# ---------------------------------------------------------------------------


def test_validate_operator_one_proof_accepts_valid_config():
    result = validate_operator_one_proof_enabled(_valid_one_proof_config())
    assert result.ok is True
    assert result.state is LiveSubmitState.OPERATOR_ONE_PROOF_ENABLED_VALID


def test_classify_operator_one_proof_state():
    state = classify_live_submit_state(_valid_one_proof_config())
    assert state is LiveSubmitState.OPERATOR_ONE_PROOF_ENABLED_VALID


def test_validate_operator_one_proof_rejects_market_orders():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(market_orders_allowed=True)
    )
    assert result.ok is False
    assert any("market_orders_allowed" in e for e in result.errors)


def test_validate_operator_one_proof_rejects_auto_run():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(auto_run=True)
    )
    assert result.ok is False
    assert any("auto_run" in e for e in result.errors)


def test_validate_operator_one_proof_rejects_weaken_gates():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(weaken_gates=True)
    )
    assert result.ok is False
    assert any("weaken_gates" in e for e in result.errors)


@pytest.mark.parametrize("missing", ["requires_command_seal", "requires_livebrokerfirewall", "requires_limit_order"])
def test_validate_operator_one_proof_rejects_missing_requirement(missing):
    config = _valid_one_proof_config()
    del config[missing]
    result = validate_operator_one_proof_enabled(config)
    assert result.ok is False
    assert any(missing in e for e in result.errors)


def test_validate_operator_one_proof_rejects_max_order_count_above_one():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(max_order_count=2)
    )
    assert result.ok is False
    assert any("max_order_count" in e for e in result.errors)


def test_validate_operator_one_proof_rejects_stale_expiry():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(expiry=past)
    )
    assert result.ok is False
    assert any("stale" in e or "expir" in e for e in result.errors)


@pytest.mark.parametrize("key", ["operator", "reason", "timestamp"])
def test_validate_operator_one_proof_rejects_missing_operator_metadata(key):
    config = _valid_one_proof_config()
    config[key] = ""
    result = validate_operator_one_proof_enabled(config)
    assert result.ok is False
    assert any(key in e for e in result.errors)


def test_validate_operator_one_proof_rejects_broad_scope():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(proof_scope="unlimited_trading")
    )
    assert result.ok is False
    assert any("proof_scope" in e for e in result.errors)


def test_validate_operator_one_proof_rejects_wrong_ack():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(explicit_acknowledgement="wrong ack")
    )
    assert result.ok is False
    assert any("ack" in e.lower() for e in result.errors)


def test_validate_operator_one_proof_rejects_scale_enabled():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(scale_enabled=True)
    )
    assert result.ok is False
    assert any("scale" in e.lower() for e in result.errors)


def test_validate_operator_one_proof_rejects_autonomy_enabled():
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(autonomy_enabled=True)
    )
    assert result.ok is False
    assert any("autonomy" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Authority context / runtime approval integration
# ---------------------------------------------------------------------------


def test_validate_operator_one_proof_with_approval_requires_scope():
    approval = {
        "scope": "one_controlled_production_pilot_via_firewall_only",
        "expiration": _future_expiry(),
    }
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(), authority_context={"approval": approval}
    )
    assert result.ok is True


def test_validate_operator_one_proof_with_bad_scope_fails():
    approval = {
        "scope": "broad_scope",
        "expiration": _future_expiry(),
    }
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(), authority_context={"approval": approval}
    )
    assert result.ok is False
    assert any("scope" in e for e in result.errors)


def test_validate_operator_one_proof_with_expired_approval_fails():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    approval = {
        "scope": "one_controlled_production_pilot_via_firewall_only",
        "expiration": past,
    }
    result = validate_operator_one_proof_enabled(
        _valid_one_proof_config(), authority_context={"approval": approval}
    )
    assert result.ok is False
    assert any("approval" in e.lower() and "expir" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Typed confirmation constant
# ---------------------------------------------------------------------------


def test_typed_confirmation_sentence_is_project_defined():
    assert "one controlled proof" in LIVE_SUBMIT_TYPED_CONFIRMATION
    assert "pass all gates" in LIVE_SUBMIT_TYPED_CONFIRMATION
