"""Broker-rejection classifier with a pre-broker/broker-transport witness rule.

Turns any failed submit attempt into an operator-actionable classification.
The core invariant: a claim of real broker contact requires transport
evidence (an HTTP status code or the ``broker_transport`` stage marker from
``predator_mesh.brokers.kalshi_errors.map_http_exception``). Local firewall
gate blocks, runner exceptions, and adapter validation errors are classified
as PRE_BROKER_GATE and must never be reported as broker rejections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

BROKER_TRANSPORT_STAGE = "broker_transport"

# Error codes that are produced entirely inside Dummy, before any broker
# transport. Sourced from live_firewall.firewall, core.live_execution_mode,
# and predator_mesh.brokers gate/validation codes.
LOCAL_GATE_CODES: frozenset[str] = frozenset(
    {
        # live_execution_mode / firewall mode gates
        "live_submit_disabled",
        "DEFAULT_DISABLED",
        "LIVE_SUBMIT_INVALID",
        "ENV_GATE_MISSING",
        "COMMAND_SEAL_NOT_READY",
        "CAPS_NOT_STRICT",
        "ADAPTER_DESCRIPTOR_NOT_STAGED",
        "CREDENTIALS_NOT_READY",
        "PROOF_LOCK_USED",
        # firewall request-level policy codes
        "MARKET_ORDER_REJECTED",
        "MARKET_ORDERS_NOT_ALLOWED",
        "MAX_ORDER_COUNT_EXCEEDED",
        "IDEMPOTENCY_KEY_MISSING",
        "PROOF_LOCK_INCOMPLETE",
        "ORDER_SIZE_CAP_EXCEEDED",
        # adapter gate/validation codes (BrokerErrorCode)
        "CREDENTIALS_ABSENT",
        "CREDENTIALS_MALFORMED",
        "RESOLVER_NOT_ARMABLE",
        "LIVE_SUBMIT_NOT_ENABLED",
        "CAPS_NOT_CONFIRMED",
        "KILL_SWITCH_ACTIVE",
        "PROOF_LOCK_REPEAT_SUBMIT",
        "LIMIT_PRICE_OUT_OF_RANGE",
        "INVALID_QUANTITY",
        "INVALID_SIDE",
        "INVALID_ACTION",
        "VENUE_REJECTED",
        "TICKER_MISSING",
        # legacy trading-path firewall reason strings (evaluate())
        "Mode is not AUTONOMOUS_LIVE_CAPPED",
        "Kill switch active",
        "Emergency stop active",
        "API key missing",
    }
)

_LOCAL_EXCEPTION_PREFIXES = (
    "RUNNER_EXCEPTION",
    "ADAPTER_EXCEPTION",
    # Retired compatibility runners/adapters deliberately fail before any
    # transport.  Keep their evidence labelled as a local gate instead of an
    # unclassified broker event.
    "LEGACY_",
)


class RejectionCategory(str, Enum):
    PRE_BROKER_GATE = "PRE_BROKER_GATE"
    AUTH_FAILED = "AUTH_FAILED"
    MARKET_NOT_FOUND = "MARKET_NOT_FOUND"
    MARKET_CLOSED = "MARKET_CLOSED"
    PRICE_TICK_INVALID = "PRICE_TICK_INVALID"
    PAYLOAD_SCHEMA_INVALID = "PAYLOAD_SCHEMA_INVALID"
    SIZE_OR_FUNDS = "SIZE_OR_FUNDS"
    RATE_LIMITED = "RATE_LIMITED"
    ACCOUNT_RESTRICTED = "ACCOUNT_RESTRICTED"
    NETWORK_TRANSPORT = "NETWORK_TRANSPORT"
    UNKNOWN_BROKER = "UNKNOWN_BROKER"
    UNCLASSIFIED_NO_WITNESS = "UNCLASSIFIED_NO_WITNESS"


_OPERATOR_ACTIONS: dict[RejectionCategory, str] = {
    RejectionCategory.PRE_BROKER_GATE: (
        "No broker contact occurred. Repair the local gate sequence (live-submit "
        "state, env gate, seal, caps, descriptor, credentials) and re-fire; the "
        "one-real-attempt budget is unspent."
    ),
    RejectionCategory.AUTH_FAILED: (
        "Broker refused credentials. Verify KALSHI_API_KEY_ID and the RSA key, "
        "signature path prefix, and system clock skew."
    ),
    RejectionCategory.MARKET_NOT_FOUND: (
        "Ticker unknown to the broker. Re-run read-only discovery and select a "
        "currently listed market; verify ticker formatting."
    ),
    RejectionCategory.MARKET_CLOSED: (
        "Market closed or not accepting orders. Select a market whose close_time "
        "is comfortably in the future and status is active."
    ),
    RejectionCategory.PRICE_TICK_INVALID: (
        "Price outside allowed range or off-tick. Re-derive price from live "
        "market metadata (min/max/tick) immediately before submit."
    ),
    RejectionCategory.PAYLOAD_SCHEMA_INVALID: (
        "Order body rejected by schema validation. Verify create-order fields "
        "(yes_price/no_price vs price, client_order_id, count, side, action)."
    ),
    RejectionCategory.SIZE_OR_FUNDS: (
        "Insufficient balance or size constraint. Check account balance and "
        "min/max order size for the market."
    ),
    RejectionCategory.RATE_LIMITED: "Rate limited. Back off and retry under a fresh authority.",
    RejectionCategory.ACCOUNT_RESTRICTED: (
        "Account-level restriction. Check account status, trading permissions, "
        "and any jurisdiction/category restrictions."
    ),
    RejectionCategory.NETWORK_TRANSPORT: (
        "Transport or broker-side 5xx failure. Confirm API base host, network "
        "path, and broker status page; retry under a fresh authority."
    ),
    RejectionCategory.UNKNOWN_BROKER: (
        "Broker rejected with an unrecognized code. Inspect error_preview and "
        "extend the classifier."
    ),
    RejectionCategory.UNCLASSIFIED_NO_WITNESS: (
        "No transport witness and unrecognized local code. Treat as no broker "
        "contact; inspect the runner/firewall logs and extend LOCAL_GATE_CODES."
    ),
}


@dataclass(frozen=True)
class RejectionClassification:
    category: RejectionCategory
    broker_contacted: bool
    pre_broker: bool
    operator_action: str
    retry_requires_new_authority: bool
    matched_on: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "broker_contacted": self.broker_contacted,
            "pre_broker": self.pre_broker,
            "operator_action": self.operator_action,
            "retry_requires_new_authority": self.retry_requires_new_authority,
            "matched_on": self.matched_on,
            "details": self.details,
        }


def _classify_http(status: int, message: str) -> RejectionCategory:
    text = (message or "").lower()
    if status in (401, 403):
        if "restrict" in text or "permission" in text:
            return RejectionCategory.ACCOUNT_RESTRICTED
        return RejectionCategory.AUTH_FAILED
    if status == 404:
        return RejectionCategory.MARKET_NOT_FOUND
    if status == 429:
        return RejectionCategory.RATE_LIMITED
    if status >= 500:
        return RejectionCategory.NETWORK_TRANSPORT
    if status == 400:
        if "closed" in text or "not open" in text or "inactive" in text or "paused" in text:
            return RejectionCategory.MARKET_CLOSED
        if "tick" in text or ("price" in text and ("invalid" in text or "range" in text or "out of" in text)):
            return RejectionCategory.PRICE_TICK_INVALID
        if "insufficient" in text or "balance" in text or "funds" in text:
            return RejectionCategory.SIZE_OR_FUNDS
        if "restrict" in text or "not allowed" in text or "forbidden" in text:
            return RejectionCategory.ACCOUNT_RESTRICTED
        if "not found" in text or "unknown market" in text or "unknown ticker" in text:
            return RejectionCategory.MARKET_NOT_FOUND
        return RejectionCategory.PAYLOAD_SCHEMA_INVALID
    return RejectionCategory.UNKNOWN_BROKER


def classify_rejection(
    error_code: str | None,
    http_status: int | str | None = None,
    safe_message: str | None = None,
    stage: str | None = None,
) -> RejectionClassification:
    """Classify a failed submit attempt.

    ``broker_contacted`` is True only with transport evidence: a numeric HTTP
    status or ``stage == "broker_transport"``.
    """
    code = (error_code or "").strip()
    status: int | None = None
    if isinstance(http_status, int):
        status = http_status
    elif isinstance(http_status, str) and http_status.strip().isdigit():
        status = int(http_status.strip())

    transport_witness = status is not None or stage == BROKER_TRANSPORT_STAGE

    if transport_witness:
        category = (
            _classify_http(status, safe_message or "")
            if status is not None
            else RejectionCategory.NETWORK_TRANSPORT
        )
        return RejectionClassification(
            category=category,
            broker_contacted=True,
            pre_broker=False,
            operator_action=_OPERATOR_ACTIONS[category],
            retry_requires_new_authority=True,
            matched_on=f"transport_witness(status={status}, stage={stage})",
            details={"error_code": code, "http_status": status, "safe_message": (safe_message or "")[:240]},
        )

    if code in LOCAL_GATE_CODES or code.startswith(_LOCAL_EXCEPTION_PREFIXES):
        return RejectionClassification(
            category=RejectionCategory.PRE_BROKER_GATE,
            broker_contacted=False,
            pre_broker=True,
            operator_action=_OPERATOR_ACTIONS[RejectionCategory.PRE_BROKER_GATE],
            retry_requires_new_authority=False,
            matched_on=f"local_gate_code({code})",
            details={"error_code": code},
        )

    return RejectionClassification(
        category=RejectionCategory.UNCLASSIFIED_NO_WITNESS,
        broker_contacted=False,
        pre_broker=True,
        operator_action=_OPERATOR_ACTIONS[RejectionCategory.UNCLASSIFIED_NO_WITNESS],
        retry_requires_new_authority=False,
        matched_on=f"no_witness({code or 'empty'})",
        details={"error_code": code},
    )
