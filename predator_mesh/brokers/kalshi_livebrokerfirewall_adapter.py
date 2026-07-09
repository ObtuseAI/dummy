"""Concrete Kalshi LiveBrokerFirewall adapter.

This adapter is fail-closed: it validates every gate and order-field
constraint before calling Kalshi, and it returns structured errors rather
than raising on broker rejections. Credentials are read from the process
environment only and are never logged or returned in diagnostics.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization

import kalshi.signer
from kalshi.client import KalshiClient
from kalshi.submitter import KalshiSubmitter

from predator_mesh.brokers.kalshi_errors import (
    BrokerErrorCode,
    map_http_exception,
)
from predator_mesh.brokers.kalshi_types import (
    kalshi_create_order_payload,
    normalize_kalshi_status,
)
from predator_mesh.brokers.livebrokerfirewall_adapter import (
    AdapterHealth,
    LimitOrderRequest,
    LiveBrokerFirewallAdapter,
    OrderState,
    OrderStatusResult,
    SubmitResult,
)

_ALLOWED_VENUES = {"KALSHI"}
_MAX_ORDER_NOTIONAL_CENTS = 100
_SAFE_BROKER_ERROR_KEYS = {"status_code", "error_preview", "adapter_error_type", "stage"}


def _redact_submit_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only the safe, non-secret broker-error diagnostic keys."""
    return {k: v for k, v in raw.items() if k in _SAFE_BROKER_ERROR_KEYS}


def _env(name: str) -> str:
    """Read an environment variable, treating empty strings as absent."""
    return os.environ.get(name, "").strip()


class KalshiLiveBrokerFirewallAdapter(LiveBrokerFirewallAdapter):
    """Real Kalshi limit-order adapter with fail-closed gates."""

    def __init__(
        self,
        *,
        live_submit_enabled: bool = False,
        caps_confirmed: bool = False,
        kill_switch_active: bool = False,
        command_seal_ready: bool = False,
        resolver_armable: bool = False,
        require_proof_lock: bool = True,
        httpx_client: httpx.AsyncClient | None = None,
        max_order_notional_cents: int = _MAX_ORDER_NOTIONAL_CENTS,
    ) -> None:
        self.live_submit_enabled = bool(live_submit_enabled)
        self.caps_confirmed = bool(caps_confirmed)
        self.kill_switch_active = bool(kill_switch_active)
        self.command_seal_ready = bool(command_seal_ready)
        self.resolver_armable = bool(resolver_armable)
        self.require_proof_lock = bool(require_proof_lock)
        # Per-order notional ceiling; the one-shot proof path keeps the 100c
        # default, the autonomy risk brain passes its own budgeted value.
        self.max_order_notional_cents = int(max_order_notional_cents)
        self._attempted = False

        # Use the same defaults as kalshi.signer so the request URL and the
        # signature prefix stay aligned.
        self._base = _env("KALSHI_API_BASE") or kalshi.signer.BASE
        self._version = _env("KALSHI_API_VERSION") or kalshi.signer.VERSION

        self._kalshi = KalshiClient()
        if httpx_client is not None:
            self._kalshi.client = httpx_client
        else:
            self._kalshi.client = httpx.AsyncClient(
                base_url=f"{self._base}/{self._version}".rstrip("/"),
                timeout=10,
            )
        # The actual broker create_order call must go through the existing
        # KalshiSubmitter so the repo's security invariant (only firewall.py
        # and submitter.py may call create_order) remains intact.
        self._submitter = KalshiSubmitter(self._kalshi)

    # ------------------------------------------------------------------
    # Environment / credentials
    # ------------------------------------------------------------------

    def _api_key_id(self) -> str:
        return _env("KALSHI_API_KEY_ID")

    def _resolve_private_key_pem(self) -> str | None:
        """Resolve the private key PEM from canonical or legacy env vars."""
        pem = _env("KALSHI_API_PRIVATE_KEY_PEM")
        if not pem:
            pem = _env("KALSHI_PRIVATE_KEY")  # legacy inline PEM
        if not pem:
            path = _env("KALSHI_API_PRIVATE_KEY_PEM_PATH") or _env(
                "KALSHI_PRIVATE_KEY_PATH"
            )
            if path and Path(path).exists():
                try:
                    pem = Path(path).read_text()
                except OSError:
                    pem = ""
        return pem if pem else None

    def _try_parse_key(self, pem: str) -> bool:
        try:
            serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
            return True
        except Exception:
            return False

    def _credential_errors(self) -> list[str]:
        errors: list[str] = []
        key_id = self._api_key_id()
        pem = self._resolve_private_key_pem()
        if not key_id:
            errors.append(BrokerErrorCode.CREDENTIALS_ABSENT)
        if not pem:
            errors.append(BrokerErrorCode.CREDENTIALS_ABSENT)
        if pem and not self._try_parse_key(pem):
            errors.append(BrokerErrorCode.CREDENTIALS_MALFORMED)
        return errors

    @contextlib.contextmanager
    def _resolved_key_env(self):
        """Temporarily expose the resolved key under the canonical env name.

        This lets kalshi.signer.sign_request work when only legacy env vars
        are configured, without permanently mutating the process environment.
        """
        pem = self._resolve_private_key_pem()
        canonical = "KALSHI_API_PRIVATE_KEY_PEM"
        original: str | None = os.environ.get(canonical)
        try:
            if pem is not None:
                os.environ[canonical] = pem
            yield
        finally:
            if pem is not None:
                if original is None:
                    os.environ.pop(canonical, None)
                else:
                    os.environ[canonical] = original

    def validate_environment(self) -> AdapterHealth:
        """Dry health check: credentials/config only, no network calls."""
        errors = self._credential_errors()
        diagnostics = self.redact_diagnostics()
        ready = len(errors) == 0
        return AdapterHealth(
            ready=ready,
            ok=ready,
            errors=errors,
            diagnostics=diagnostics,
        )

    def redact_diagnostics(self) -> dict[str, Any]:
        """Return diagnostics with no credential material."""
        pem = self._resolve_private_key_pem()
        return {
            "venue": "KALSHI",
            "base_url": self._redact_base_url(self._base),
            "api_version": self._version,
            "key_id_present": bool(self._api_key_id()),
            "key_loaded": bool(pem) and self._try_parse_key(pem),
            "live_submit_enabled": self.live_submit_enabled,
            "caps_confirmed": self.caps_confirmed,
            "kill_switch_active": self.kill_switch_active,
            "command_seal_ready": self.command_seal_ready,
            "resolver_armable": self.resolver_armable,
            "require_proof_lock": self.require_proof_lock,
            "attempted": self._attempted,
        }

    @staticmethod
    def _redact_base_url(url: str) -> str:
        """Keep only the scheme and host for diagnostics."""
        try:
            parts = url.split("//", 1)
            if len(parts) == 2:
                remainder = parts[1].split("/", 1)[0]
                return f"{parts[0]}//{remainder}"
            return url
        except Exception:
            return "<redacted>"

    # ------------------------------------------------------------------
    # Request validation and gates
    # ------------------------------------------------------------------

    def _validate_request(self, req: LimitOrderRequest) -> list[str]:
        errors: list[str] = []

        if req.venue.upper() not in _ALLOWED_VENUES:
            errors.append(BrokerErrorCode.VENUE_REJECTED)
        if req.order_type.upper() != "LIMIT":
            errors.append(BrokerErrorCode.MARKET_ORDER_REJECTED)
        if req.market_orders_allowed:
            errors.append(BrokerErrorCode.MARKET_ORDERS_NOT_ALLOWED)
        if not req.idempotency_key:
            errors.append(BrokerErrorCode.IDEMPOTENCY_KEY_MISSING)
        if req.proof_id or req.proof_target:
            if not req.proof_id or not req.proof_target:
                errors.append(BrokerErrorCode.PROOF_LOCK_INCOMPLETE)
        if not (1 <= req.price <= 99):
            errors.append(BrokerErrorCode.LIMIT_PRICE_OUT_OF_RANGE)
        if req.quantity < 1:
            errors.append(BrokerErrorCode.INVALID_QUANTITY)
        if req.price * req.quantity > self.max_order_notional_cents:
            errors.append(BrokerErrorCode.ORDER_SIZE_CAP_EXCEEDED)
        if req.max_order_count != 1:
            errors.append(BrokerErrorCode.MAX_ORDER_COUNT_EXCEEDED)
        if req.side not in ("yes", "no"):
            errors.append(BrokerErrorCode.INVALID_SIDE)
        if req.action not in ("buy", "sell"):
            errors.append(BrokerErrorCode.INVALID_ACTION)
        if not req.market_ticker:
            errors.append(BrokerErrorCode.TICKER_MISSING)

        return errors

    def _gate_errors(self) -> list[str]:
        errors: list[str] = []
        if self._attempted:
            errors.append(BrokerErrorCode.PROOF_LOCK_REPEAT_SUBMIT)
        if not self.command_seal_ready:
            errors.append(BrokerErrorCode.COMMAND_SEAL_NOT_READY)
        if not self.resolver_armable:
            errors.append(BrokerErrorCode.RESOLVER_NOT_ARMABLE)
        if not self.live_submit_enabled:
            errors.append(BrokerErrorCode.LIVE_SUBMIT_NOT_ENABLED)
        if not self.caps_confirmed:
            errors.append(BrokerErrorCode.CAPS_NOT_CONFIRMED)
        if self.kill_switch_active:
            errors.append(BrokerErrorCode.KILL_SWITCH_ACTIVE)
        return errors

    # ------------------------------------------------------------------
    # Public adapter interface
    # ------------------------------------------------------------------

    async def submit_limit_order(self, order: LimitOrderRequest) -> SubmitResult:
        """Validate, gate, and submit a limit order to Kalshi."""
        validation_errors = self._validate_request(order)
        if validation_errors:
            return SubmitResult(
                submitted=False,
                order_id=None,
                state=OrderState.REJECTED,
                raw={},
                errors=validation_errors,
            )

        gate_errors = self._gate_errors()
        if gate_errors:
            return SubmitResult(
                submitted=False,
                order_id=None,
                state=OrderState.REJECTED,
                raw={},
                errors=gate_errors,
            )

        credential_errors = self._credential_errors()
        if credential_errors:
            return SubmitResult(
                submitted=False,
                order_id=None,
                state=OrderState.REJECTED,
                raw={},
                errors=credential_errors,
            )

        self._attempted = True

        payload = kalshi_create_order_payload(order)
        try:
            with self._resolved_key_env():
                raw = await self._submitter.submit_limit_order(payload)
        except Exception as exc:
            summary = map_http_exception(exc)
            return SubmitResult(
                submitted=False,
                order_id=None,
                state=OrderState.REJECTED,
                raw=_redact_submit_raw(summary.raw),
                errors=[summary.code],
            )

        order_id = str(raw.get("order_id") or raw.get("id") or "")
        state = normalize_kalshi_status(raw.get("status"))
        return SubmitResult(
            submitted=True,
            order_id=order_id,
            state=state,
            raw=raw,
            errors=[],
        )

    async def get_order_status(self, order_id: str) -> OrderStatusResult:
        """Fetch a single order's status and normalize it."""
        if not order_id:
            return OrderStatusResult(
                order_id="",
                state=OrderState.UNKNOWN,
                raw={},
                errors=[BrokerErrorCode.IDEMPOTENCY_KEY_MISSING],
            )

        credential_errors = self._credential_errors()
        if credential_errors:
            return OrderStatusResult(
                order_id=order_id,
                state=OrderState.UNKNOWN,
                raw={},
                errors=credential_errors,
            )

        try:
            with self._resolved_key_env():
                raw = await self._kalshi._request(
                    "GET", f"/portfolio/orders/{order_id}"
                )
        except Exception as exc:
            summary = map_http_exception(exc)
            return OrderStatusResult(
                order_id=order_id,
                state=OrderState.UNKNOWN,
                raw=summary.raw,
                errors=[summary.code],
            )

        state = normalize_kalshi_status(raw.get("status"))
        return OrderStatusResult(
            order_id=str(raw.get("order_id") or order_id),
            state=state,
            raw=raw,
            errors=[],
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._kalshi.close()
