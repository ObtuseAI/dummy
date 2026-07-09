"""Generic LiveBrokerFirewall adapter protocol and common order types.

Adapters implementing this protocol are responsible for enforcing the
firewall boundary around real broker order submission:
  * limit orders only
  * strict caps
  * required idempotency / proof metadata
  * fail-closed behaviour on any validation or broker error
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LiveBrokerFirewallError(RuntimeError):
    """Raised for unrecoverable fail-closed conditions."""


class OrderState:
    """Normalized order lifecycle states returned by all adapters."""

    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    PARTIAL_FILL = "PARTIAL_FILL"
    OPEN = "OPEN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class LimitOrderRequest:
    """Normalized limit-order request accepted by the firewall adapter."""

    venue: str
    order_type: str  # must be "LIMIT"
    market_orders_allowed: bool  # must be False
    side: str  # "yes" | "no"
    action: str  # "buy" | "sell"
    price: int  # cents, 1..99
    quantity: int  # contracts, >=1
    idempotency_key: str  # required
    market_ticker: str
    proof_id: str | None = None
    proof_target: str | None = None
    client_order_id: str | None = None
    max_order_count: int = 1
    max_order_size_cents: int = 100
    # Exchange-enforced TTL (unix seconds). Stale maker quotes expire on the
    # exchange instead of requiring a cancel call, which the repo's
    # no-direct-cancel-bypass gates forbid.
    expiration_ts: int | None = None


@dataclass(frozen=True)
class AdapterHealth:
    """Dry/no-contact health result from validate_environment()."""

    ready: bool  # credentials/config are present and well-formed
    ok: bool  # no errors were detected
    errors: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmitResult:
    """Result of a limit-order submission attempt."""

    submitted: bool
    order_id: str | None
    state: str
    raw: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrderStatusResult:
    """Normalized order status lookup result."""

    order_id: str
    state: str
    raw: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class LiveBrokerFirewallAdapter(ABC):
    """Base interface for a real, fail-closed live broker adapter."""

    @abstractmethod
    def validate_environment(self) -> AdapterHealth:
        """Dry health check: verify credentials/config without network calls."""
        ...

    @abstractmethod
    async def submit_limit_order(self, order: LimitOrderRequest) -> SubmitResult:
        """Submit a limit order after enforcing all firewall gates."""
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatusResult:
        """Fetch and normalize a single order's status."""
        ...

    @abstractmethod
    def redact_diagnostics(self) -> dict[str, Any]:
        """Return redacted diagnostics containing no secrets."""
        ...
