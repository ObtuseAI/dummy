"""Operator-fill skeleton for a REAL LiveBrokerFirewall order adapter.

THIS IS A SKELETON. It intentionally does NOT place any real order. The single
live network call is left as an explicit, guarded TODO that raises until the
operator wires it. Everything around that call — credential loading, fail-closed
gates, limit-only enforcement, kill-switch, single-attempt lock — is implemented
so the operator only has to (a) supply credentials via environment and (b) fill
the one marked method with the broker's real limit-order endpoint call.

Boundaries baked in (do not remove):
  * limit orders only — market orders are rejected before any network activity.
  * fail-closed — any missing gate raises and submits nothing.
  * kill-switch honored — an active kill-switch blocks submission.
  * single attempt — an idempotency key guards against repeat submits.
  * no credentials in source — keys are read from os.environ only.

The seal/resolver/firewall gates elsewhere in Dummy still apply on top of this.
This adapter never self-authorizes; it only executes once every upstream gate
has already passed and the operator has explicitly enabled live-submit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class LiveBrokerFirewallError(RuntimeError):
    """Raised for any fail-closed condition. Submitting nothing is the safe path."""


# Credential env var names. The operator sets these in their own shell/secret
# store. They are never written to disk or logged.
CREDENTIAL_ENV_VARS = ("KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY")


@dataclass(frozen=True)
class LimitOrderRequest:
    market_ticker: str
    side: str            # "yes" | "no"
    action: str          # "buy" | "sell"
    count: int           # contracts
    limit_price_cents: int   # 1..99, limit only
    idempotency_key: str


@dataclass(frozen=True)
class SubmitResult:
    submitted: bool
    order_id: str | None
    state: str           # FILLED | RESTING | REJECTED | CANCELED | ...
    raw: dict[str, Any]


class LiveBrokerFirewallAdapter:
    """Real limit-order adapter, operator-completed.

    Construct with the runtime gate signals already resolved upstream. The
    adapter re-checks every one of them and refuses to submit if any is false —
    it trusts nothing.
    """

    def __init__(
        self,
        *,
        live_submit_enabled: bool,
        caps_confirmed: bool,
        kill_switch_active: bool,
        command_seal_ready: bool,
        resolver_armable: bool,
    ) -> None:
        self.live_submit_enabled = bool(live_submit_enabled)
        self.caps_confirmed = bool(caps_confirmed)
        self.kill_switch_active = bool(kill_switch_active)
        self.command_seal_ready = bool(command_seal_ready)
        self.resolver_armable = bool(resolver_armable)
        self._attempted = False

    # ---------------- credentials ----------------

    def _load_credentials(self) -> dict[str, str]:
        creds = {name: os.environ.get(name, "") for name in CREDENTIAL_ENV_VARS}
        missing = [name for name, val in creds.items() if not val]
        if missing:
            raise LiveBrokerFirewallError(
                f"CREDENTIALS_ABSENT: set {', '.join(missing)} in the environment. "
                "Never hardcode keys."
            )
        return creds

    # ---------------- fail-closed gate ----------------

    def _assert_armable(self, req: LimitOrderRequest) -> None:
        if self._attempted:
            raise LiveBrokerFirewallError("PROOF_LOCK: one attempt already made; refusing repeat submit.")
        if not self.command_seal_ready:
            raise LiveBrokerFirewallError("COMMAND_SEAL_NOT_READY")
        if not self.resolver_armable:
            raise LiveBrokerFirewallError("RESOLVER_NOT_ARMABLE")
        if not self.live_submit_enabled:
            raise LiveBrokerFirewallError("LIVE_SUBMIT_NOT_ENABLED")
        if not self.caps_confirmed:
            raise LiveBrokerFirewallError("CAPS_NOT_CONFIRMED")
        if self.kill_switch_active:
            raise LiveBrokerFirewallError("KILL_SWITCH_ACTIVE")
        if not (1 <= req.limit_price_cents <= 99):
            raise LiveBrokerFirewallError("LIMIT_PRICE_OUT_OF_RANGE")
        if req.count < 1:
            raise LiveBrokerFirewallError("INVALID_COUNT")
        if req.action not in ("buy", "sell") or req.side not in ("yes", "no"):
            raise LiveBrokerFirewallError("INVALID_ORDER_SHAPE")
        if not req.idempotency_key:
            raise LiveBrokerFirewallError("IDEMPOTENCY_KEY_MISSING")

    # ---------------- the one method the operator fills ----------------

    def _place_limit_order_live(self, req: LimitOrderRequest, creds: dict[str, str]) -> dict[str, Any]:
        """OPERATOR: implement the single real limit-order call here.

        Fill with the authenticated Kalshi CreateOrder call, order_type="limit"
        only. Return the broker's raw JSON response. Do NOT add a market-order
        branch. Do NOT catch-and-ignore errors — let them propagate so the
        fail-closed path submits nothing on failure.

        Until implemented, this raises so the skeleton can never place an order.
        """
        raise LiveBrokerFirewallError(
            "LIVE_CALL_NOT_IMPLEMENTED: operator must implement _place_limit_order_live "
            "with the real Kalshi limit-order endpoint before any live proof."
        )

    # ---------------- public entry ----------------

    def submit_limit_order(self, req: LimitOrderRequest) -> SubmitResult:
        self._assert_armable(req)
        creds = self._load_credentials()
        self._attempted = True  # lock before the call: one attempt, win or lose
        raw = self._place_limit_order_live(req, creds)
        return SubmitResult(
            submitted=True,
            order_id=str(raw.get("order_id") or raw.get("id") or ""),
            state=str(raw.get("status") or raw.get("state") or "UNKNOWN").upper(),
            raw=raw,
        )
