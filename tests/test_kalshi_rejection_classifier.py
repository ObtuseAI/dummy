"""Tests for the broker-rejection classifier and its contact-witness rule."""

from __future__ import annotations

import pytest

from kalshi.rejection_classifier import (
    LOCAL_GATE_CODES,
    RejectionCategory,
    classify_rejection,
)


# --- Pre-broker local gates: never claim broker contact ---


@pytest.mark.parametrize(
    "code",
    [
        "live_submit_disabled",
        "ENV_GATE_MISSING",
        "COMMAND_SEAL_NOT_READY",
        "CAPS_NOT_STRICT",
        "CREDENTIALS_NOT_READY",
        "CREDENTIALS_ABSENT",
        "KILL_SWITCH_ACTIVE",
        "MARKET_ORDER_REJECTED",
        "ORDER_SIZE_CAP_EXCEEDED",
        "PROOF_LOCK_USED",
    ],
)
def test_local_gate_codes_are_pre_broker(code):
    result = classify_rejection(code)
    assert result.category is RejectionCategory.PRE_BROKER_GATE
    assert result.broker_contacted is False
    assert result.pre_broker is True
    assert result.retry_requires_new_authority is False


def test_runner_exception_is_pre_broker():
    result = classify_rejection("RUNNER_EXCEPTION:NameError")
    assert result.category is RejectionCategory.PRE_BROKER_GATE
    assert result.broker_contacted is False


def test_adapter_exception_is_pre_broker():
    result = classify_rejection("ADAPTER_EXCEPTION:TimeoutError")
    assert result.broker_contacted is False


def test_unknown_code_without_witness_never_claims_contact():
    result = classify_rejection("SOMETHING_NEW_AND_UNKNOWN")
    assert result.category is RejectionCategory.UNCLASSIFIED_NO_WITNESS
    assert result.broker_contacted is False
    assert result.pre_broker is True


def test_empty_code_without_witness():
    result = classify_rejection(None)
    assert result.broker_contacted is False


# --- Transport witnesses: broker contact confirmed ---


def test_http_status_is_a_contact_witness():
    result = classify_rejection("BROKER_VALIDATION", http_status=400)
    assert result.broker_contacted is True
    assert result.pre_broker is False
    assert result.retry_requires_new_authority is True


def test_broker_transport_stage_is_a_contact_witness():
    result = classify_rejection("BROKER_ERROR", stage="broker_transport")
    assert result.broker_contacted is True
    assert result.category is RejectionCategory.NETWORK_TRANSPORT


def test_string_http_status_is_accepted():
    result = classify_rejection("BROKER_VALIDATION", http_status="404")
    assert result.broker_contacted is True
    assert result.category is RejectionCategory.MARKET_NOT_FOUND


# --- HTTP status/message mapping ---


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (401, "", RejectionCategory.AUTH_FAILED),
        (403, "", RejectionCategory.AUTH_FAILED),
        (403, "account restricted in your region", RejectionCategory.ACCOUNT_RESTRICTED),
        (404, "market not found", RejectionCategory.MARKET_NOT_FOUND),
        (429, "too many requests", RejectionCategory.RATE_LIMITED),
        (500, "internal", RejectionCategory.NETWORK_TRANSPORT),
        (503, "unavailable", RejectionCategory.NETWORK_TRANSPORT),
        (400, "market is closed", RejectionCategory.MARKET_CLOSED),
        (400, "price out of range", RejectionCategory.PRICE_TICK_INVALID),
        (400, "invalid tick", RejectionCategory.PRICE_TICK_INVALID),
        (400, "insufficient balance", RejectionCategory.SIZE_OR_FUNDS),
        (400, "trading not allowed for this account", RejectionCategory.ACCOUNT_RESTRICTED),
        (400, "missing field yes_price", RejectionCategory.PAYLOAD_SCHEMA_INVALID),
    ],
)
def test_http_mapping(status, message, expected):
    result = classify_rejection("BROKER_X", http_status=status, safe_message=message)
    assert result.category is expected
    assert result.broker_contacted is True


def test_every_local_gate_code_maps_pre_broker():
    for code in LOCAL_GATE_CODES:
        assert classify_rejection(code).broker_contacted is False, code


def test_to_dict_round_trip():
    result = classify_rejection("live_submit_disabled")
    data = result.to_dict()
    assert data["category"] == "PRE_BROKER_GATE"
    assert data["broker_contacted"] is False
    assert "operator_action" in data and data["operator_action"]
