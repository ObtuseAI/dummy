"""Live broker firewall adapters for order submission.

This package exposes the generic LiveBrokerFirewall adapter protocol and a
concrete Kalshi implementation. All adapters are fail-closed and read
credentials exclusively from the process environment.
"""

from __future__ import annotations

from predator_mesh.brokers.livebrokerfirewall_adapter import (
    AdapterHealth,
    LimitOrderRequest,
    LiveBrokerFirewallAdapter,
    LiveBrokerFirewallError,
    OrderState,
    OrderStatusResult,
    SubmitResult,
)
from predator_mesh.brokers.kalshi_errors import (
    BrokerErrorCode,
    LiveBrokerError,
    map_http_exception,
)
from predator_mesh.brokers.kalshi_livebrokerfirewall_adapter import (
    KalshiLiveBrokerFirewallAdapter,
)
from predator_mesh.brokers.kalshi_types import (
    KalshiCreateOrderPayload,
    normalize_kalshi_status,
)

__all__ = [
    "AdapterHealth",
    "BrokerErrorCode",
    "KalshiCreateOrderPayload",
    "KalshiLiveBrokerFirewallAdapter",
    "LimitOrderRequest",
    "LiveBrokerError",
    "LiveBrokerFirewallAdapter",
    "LiveBrokerFirewallError",
    "OrderState",
    "OrderStatusResult",
    "SubmitResult",
    "map_http_exception",
    "normalize_kalshi_status",
]
