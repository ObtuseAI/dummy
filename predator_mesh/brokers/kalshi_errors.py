"""Structured error types and HTTP-to-broker error mapping for Kalshi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from kalshi.error_classifier import classify


class BrokerErrorCode:
    """String error codes used in SubmitResult / OrderStatusResult.errors."""

    CREDENTIALS_ABSENT = "CREDENTIALS_ABSENT"
    CREDENTIALS_MALFORMED = "CREDENTIALS_MALFORMED"
    COMMAND_SEAL_NOT_READY = "COMMAND_SEAL_NOT_READY"
    RESOLVER_NOT_ARMABLE = "RESOLVER_NOT_ARMABLE"
    LIVE_SUBMIT_NOT_ENABLED = "LIVE_SUBMIT_NOT_ENABLED"
    CAPS_NOT_CONFIRMED = "CAPS_NOT_CONFIRMED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    PROOF_LOCK_REPEAT_SUBMIT = "PROOF_LOCK_REPEAT_SUBMIT"
    PROOF_LOCK_INCOMPLETE = "PROOF_LOCK_INCOMPLETE"
    MARKET_ORDER_REJECTED = "MARKET_ORDER_REJECTED"
    MARKET_ORDERS_NOT_ALLOWED = "MARKET_ORDERS_NOT_ALLOWED"
    IDEMPOTENCY_KEY_MISSING = "IDEMPOTENCY_KEY_MISSING"
    LIMIT_PRICE_OUT_OF_RANGE = "LIMIT_PRICE_OUT_OF_RANGE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    ORDER_SIZE_CAP_EXCEEDED = "ORDER_SIZE_CAP_EXCEEDED"
    MAX_ORDER_COUNT_EXCEEDED = "MAX_ORDER_COUNT_EXCEEDED"
    INVALID_SIDE = "INVALID_SIDE"
    INVALID_ACTION = "INVALID_ACTION"
    VENUE_REJECTED = "VENUE_REJECTED"
    TICKER_MISSING = "TICKER_MISSING"
    BROKER_ERROR = "BROKER_ERROR"


class LiveBrokerError(RuntimeError):
    """Structured adapter error carrying a machine-readable code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class ErrorSummary:
    code: str
    raw: dict[str, Any]


_BROKER_TRANSPORT_STAGE = "broker_transport"


def map_http_exception(exc: Exception) -> ErrorSummary:
    """Map an exception from the broker transport to a structured error.

    The returned ``raw`` dict contains only safe, non-secret keys so it can
    be forwarded to reports and dashboards without redaction risk.
    """
    adapter_error_type = f"{type(exc).__module__}.{type(exc).__name__}"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        category = classify(status, exc.response.text)
        return ErrorSummary(
            code=f"BROKER_{category.value}",
            raw={
                "status_code": status,
                "error_preview": exc.response.text[:240],
                "adapter_error_type": adapter_error_type,
                "stage": _BROKER_TRANSPORT_STAGE,
            },
        )
    return ErrorSummary(
        code=BrokerErrorCode.BROKER_ERROR,
        raw={
            "status_code": None,
            "error_preview": str(exc)[:240],
            "adapter_error_type": adapter_error_type,
            "stage": _BROKER_TRANSPORT_STAGE,
        },
    )
