"""Read-only Kalshi market/payload validator.

No order submits, cancels, or writes. Supports no_network, mock, and
read_only_network modes.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from kalshi.client import KalshiClient

from core.read_only_transport_guard import ReadOnlyTransportGuard


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    field: str | None = None

    @property
    def error_message(self) -> str | None:
        return "; ".join(self.errors) if self.errors else None


@dataclass(frozen=True)
class ContractMetadata:
    ticker: str
    status: str
    tradable: bool


@dataclass(frozen=True)
class MarketMetadata:
    ticker: str
    status: str
    open_time: str | None
    close_time: str | None
    trading_allowed: bool
    min_price_cents: int
    max_price_cents: int
    tick_size_cents: int
    contracts: list[ContractMetadata]


# Kalshi tickers are opaque identifiers, not OCC option symbols. Current
# market/event families include long KX... multi-leg ids and legacy INX/INFX
# series; dots can appear in numeric thresholds. Keep this shape strict enough
# to reject whitespace, paths, control characters, and synthetic local ids.
_MARKET_TICKER_RE = re.compile(r"^(?:KX|INX|INFX)[A-Z0-9-][A-Z0-9._-]{1,198}$")


def _safe_upper(value: Any) -> str:
    return str(value).strip().upper() if value is not None else ""


def validate_ticker_shape(market_ticker: str, contract_ticker: str | None = None) -> ValidationResult:
    errors: list[str] = []
    if not market_ticker or not isinstance(market_ticker, str):
        errors.append("market_ticker is required and must be a non-empty string")
    elif not _MARKET_TICKER_RE.match(market_ticker.strip().upper()):
        errors.append("market_ticker does not match expected Kalshi shape")

    if contract_ticker is not None:
        if not isinstance(contract_ticker, str) or not contract_ticker.strip():
            errors.append("contract_ticker is required and must be a non-empty string")
        elif contract_ticker.strip().upper() != market_ticker.strip().upper():
            # For Kalshi yes/no markets the contract ticker equals market ticker.
            errors.append("contract_ticker must match market_ticker for yes/no markets")

    return ValidationResult(ok=not errors, errors=errors, field="ticker" if errors else None)


def validate_order_payload_shape(payload: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    required = {"ticker", "side", "action", "type", "count", "price", "client_order_id"}
    missing = required - set(payload.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    for key in payload:
        if payload[key] is None and key in required:
            errors.append(f"required field {key} is null")

    if payload.get("type", "").upper() != "LIMIT":
        errors.append("order type must be LIMIT")

    side = _safe_upper(payload.get("side"))
    if side not in {"YES", "NO"}:
        errors.append("side must be yes or no")

    action = _safe_upper(payload.get("action"))
    if action not in {"BUY", "SELL"}:
        errors.append("action must be buy or sell")

    count = payload.get("count")
    if not isinstance(count, int) or count < 1:
        errors.append("count must be a positive integer")
    elif count != 1:
        errors.append("count must equal 1 for proof candidate")

    price = payload.get("price")
    if not isinstance(price, int) or price < 1 or price > 99:
        errors.append("price must be an integer cent value in [1, 99]")

    client_order_id = payload.get("client_order_id")
    if not client_order_id or not isinstance(client_order_id, str):
        errors.append("client_order_id / idempotency key is required")

    unknown = set(payload.keys()) - required - {"idempotency_key", "proof_id", "proof_target"}
    if unknown:
        errors.append(f"unknown fields present: {sorted(unknown)}")

    return ValidationResult(ok=not errors, errors=errors, field="payload" if errors else None)


def fetch_market_metadata_read_only(
    market_ticker: str,
    mode: str = "no_network",
    client: Any | None = None,
) -> MarketMetadata | None:
    """Return market metadata without submitting any order.

    Modes:
      - no_network: return None (schema-only callers should tolerate None).
      - mock: return a canned open metadata for the ticker if shape-valid.
      - read_only_network: perform a GET to Kalshi market endpoint via `client`.
    """
    shape = validate_ticker_shape(market_ticker)
    if not shape.ok:
        return None

    ticker = market_ticker.strip().upper()

    if mode == "no_network":
        return None

    if mode == "mock":
        return MarketMetadata(
            ticker=ticker,
            status="open",
            open_time=None,
            close_time=None,
            trading_allowed=True,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[ContractMetadata(ticker=ticker, status="open", tradable=True)],
        )

    if mode == "read_only_network":
        if client is None:
            return None
        # Delegates to a read-only client method; no POST/order calls here.
        return client.get_market(ticker)

    return None


def fetch_contract_metadata_read_only(
    contract_ticker: str,
    mode: str = "no_network",
    client: Any | None = None,
) -> ContractMetadata | None:
    shape = validate_ticker_shape(contract_ticker, contract_ticker)
    if not shape.ok:
        return None
    if mode == "no_network":
        return None
    if mode == "mock":
        return ContractMetadata(ticker=contract_ticker.upper(), status="open", tradable=True)
    if mode == "read_only_network":
        if client is None:
            return None
        return client.get_contract(contract_ticker)
    return None


def validate_payload_against_metadata(
    payload: dict[str, Any],
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
) -> ValidationResult:
    errors: list[str] = []

    shape = validate_order_payload_shape(payload)
    if not shape.ok:
        errors.extend(shape.errors)

    market_ticker = payload.get("ticker", "").strip().upper()
    if market_ticker != metadata.ticker.upper():
        errors.append("payload ticker does not match metadata ticker")

    if not metadata.trading_allowed or metadata.status.lower() != "open":
        errors.append("market is not open for trading")

    price = payload.get("price")
    if isinstance(price, int):
        if price < metadata.min_price_cents or price > metadata.max_price_cents:
            errors.append(
                f"price {price} outside market bounds "
                f"[{metadata.min_price_cents}, {metadata.max_price_cents}]"
            )
        if (price - metadata.min_price_cents) % metadata.tick_size_cents != 0:
            errors.append(f"price {price} is not on tick size {metadata.tick_size_cents}")

    contract = next(
        (c for c in metadata.contracts if c.ticker.upper() == market_ticker),
        None,
    )
    if contract is None:
        errors.append("contract not found in market metadata")
    elif not contract.tradable or contract.status.lower() != "open":
        errors.append("contract is not tradable/open")

    count = payload.get("count")
    caps_max = caps.get("max_order_count", 1) if caps else 1
    if isinstance(count, int) and count > caps_max:
        errors.append(f"count {count} exceeds caps max_order_count {caps_max}")

    return ValidationResult(ok=not errors, errors=errors, field="metadata" if errors else None)


class KalshiReadOnlyMetadataClient:
    """Wrap ``KalshiClient`` so only read-only market metadata calls reach Kalshi.

    The wrapper replaces the underlying httpx transport with a
    ``ReadOnlyTransportGuard``.  Write paths such as ``create_order`` and
    ``cancel_order`` are still present on the wrapped ``KalshiClient``, but
    any request they issue is blocked at the transport layer.
    """

    def __init__(self, client: KalshiClient | None = None):
        self._client = client or KalshiClient()
        self._original_transport = self._client.client
        self._guard = ReadOnlyTransportGuard(client=self._original_transport)
        self._client.client = self._guard

    @property
    def request_audit_log(self) -> list[dict[str, Any]]:
        return list(getattr(self._client, "request_audit_log", []))

    @property
    def blocked_attempts(self) -> list[dict[str, Any]]:
        return list(self._guard.blocked_attempts)

    async def get_markets(self) -> Any:
        return await self._client.get_markets()

    async def get_market(self, ticker: str) -> Any:
        """Fetch a single market, unwrapping both direct and nested shapes."""
        raw = await self._client.get_market(ticker)
        if isinstance(raw, dict) and "market" in raw and isinstance(raw["market"], dict):
            return raw["market"]
        return raw

    async def get_contract(self, contract_ticker: str) -> Any:
        """Fetch the market and extract the matching contract payload.

        Yes/no Kalshi markets expose the contract as the market itself, so we
        resolve it from the market response rather than requiring a dedicated
        contract endpoint on the wrapped client.
        """
        market = await self.get_market(contract_ticker)
        if not isinstance(market, dict):
            return None
        for contract in market.get("contracts", [market]):
            if not isinstance(contract, dict):
                continue
            if contract.get("ticker", "").upper() == contract_ticker.upper():
                return contract
        return None

    def get_market_sync(self, ticker: str) -> Any:
        """Sync convenience wrapper for CLI callers."""
        return asyncio.run(self.get_market(ticker))

    def http_summary(self) -> dict[str, Any]:
        """Safe summary of HTTP traffic for audit reports."""
        log = self.request_audit_log
        methods: dict[str, int] = {}
        path_families: set[str] = set()
        status_classes: set[str] = set()
        for entry in log:
            methods[entry.get("method", "UNKNOWN")] = methods.get(entry.get("method", "UNKNOWN"), 0) + 1
            path_families.add(entry.get("path_family", "unknown"))
            status_classes.add(entry.get("status_class", "unknown"))
        return {
            "total_requests": len(log),
            "methods": methods,
            "path_families": sorted(path_families),
            "status_classes": sorted(status_classes),
        }

    async def close(self) -> None:
        await self._client.close()


def _int_from_market(value: Any, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value * 100))
    if isinstance(value, str):
        try:
            return int(round(float(value) * 100))
        except (TypeError, ValueError):
            return fallback
    return fallback


def _normalize_market_status(status: str | None) -> str:
    """Map Kalshi status strings to a canonical open/closed vocabulary."""
    if not status:
        return "unknown"
    s = str(status).strip().lower()
    if s in {"open", "active", "trading", "live"}:
        return "open"
    if s in {"closed", "settled", "expired", "cancelled", "canceled", "halted", "suspended"}:
        return "closed"
    return s


def _price_bounds_from_ranges(price_ranges: Any) -> tuple[int | None, int | None, int | None]:
    """Parse Kalshi v2 ``price_ranges`` (dollar strings) into cent ints.

    Returns ``(min_price_cents, max_price_cents, tick_size_cents)`` or
    ``(None, None, None)`` if the shape is unsupported.
    """
    if not isinstance(price_ranges, list) or not price_ranges:
        return None, None, None
    first = price_ranges[0]
    if not isinstance(first, dict):
        return None, None, None
    try:
        start = float(first.get("start", 0))
        end = float(first.get("end", 0))
        step = float(first.get("step", 0))
    except (TypeError, ValueError):
        return None, None, None
    if step <= 0 or start < 0 or end <= 0:
        return None, None, None
    if end > 1.0:
        end = 1.0
    min_cents = max(1, int(round(start * 100))) if start is not None else 1
    max_cents = min(99, int(round(end * 100))) if end is not None else 99
    tick_cents = max(1, int(round(step * 100)))
    if tick_cents < 1:
        tick_cents = 1
    return min_cents, max_cents, tick_cents


def _market_metadata_from_api(market: Any) -> MarketMetadata | None:
    """Build a ``MarketMetadata`` from a Kalshi market API object.

    Accepts several common field names and both legacy/v1 cent fields and
    v2 trade-api dollar-decimal representations (``price_ranges``,
    ``price_level_structure``).
    """
    if not isinstance(market, dict):
        return None

    ticker = str(market.get("ticker", "")).strip().upper()
    if not ticker:
        return None

    status = _normalize_market_status(market.get("status"))
    open_time = market.get("open_time") or market.get("open_ts")
    close_time = market.get("close_time") or market.get("close_ts")

    explicit_trading = market.get("trading_allowed")
    if explicit_trading is not None:
        trading_allowed = bool(explicit_trading)
    else:
        trading_allowed = status == "open"

    min_price_cents = market.get("min_price_cents")
    max_price_cents = market.get("max_price_cents")
    tick_size_cents = market.get("tick_size_cents")

    has_explicit_bounds = (
        min_price_cents is not None
        and max_price_cents is not None
        and tick_size_cents is not None
    )
    price_ranges = market.get("price_ranges")

    if not has_explicit_bounds:
        range_min, range_max, range_tick = _price_bounds_from_ranges(price_ranges)
        if range_min is None and price_ranges is not None:
            # price_ranges key present but malformed → cannot validate this market.
            return None
        if min_price_cents is None:
            min_price_cents = _int_from_market(market.get("min_price"), range_min)
        if max_price_cents is None:
            max_price_cents = _int_from_market(market.get("max_price"), range_max)
        if tick_size_cents is None:
            tick_size_cents = _int_from_market(market.get("tick_size"), range_tick)

    if min_price_cents is None:
        min_price_cents = 1
    if max_price_cents is None:
        max_price_cents = 99
    if tick_size_cents is None:
        tick_size_cents = 1

    try:
        min_price_cents = int(min_price_cents)
        max_price_cents = int(max_price_cents)
        tick_size_cents = int(tick_size_cents)
    except (TypeError, ValueError):
        return None

    if min_price_cents < 1:
        min_price_cents = 1
    if max_price_cents > 99:
        max_price_cents = 99
    if tick_size_cents < 1:
        tick_size_cents = 1

    contracts_raw = market.get("contracts")
    if isinstance(contracts_raw, list) and contracts_raw:
        contracts = []
        for contract in contracts_raw:
            if not isinstance(contract, dict):
                continue
            contract_ticker = str(contract.get("ticker", ticker)).strip().upper()
            contract_status = _normalize_market_status(contract.get("status", status))
            contract_tradable = bool(
                contract.get("tradable", contract.get("active", contract_status == "open"))
            )
            contracts.append(
                ContractMetadata(
                    ticker=contract_ticker,
                    status=contract_status,
                    tradable=contract_tradable,
                )
            )
    else:
        contracts = [
            ContractMetadata(ticker=ticker, status=status, tradable=trading_allowed)
        ]

    return MarketMetadata(
        ticker=ticker,
        status=status,
        open_time=str(open_time) if open_time is not None else None,
        close_time=str(close_time) if close_time is not None else None,
        trading_allowed=trading_allowed,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        tick_size_cents=tick_size_cents,
        contracts=contracts,
    )


def derive_validated_price(metadata: MarketMetadata | None) -> tuple[int, bool, str]:
    """Derive the lowest-risk proof-candidate price from market metadata.

    Returns ``(price, price_validated, price_source)``.  If the market is
    unavailable, closed, or lacks usable price bounds, returns a safe
    fallback of ``1`` with ``price_validated=False`` and
    ``price_source="metadata_unavailable"``.
    """
    if metadata is None:
        return 1, False, "metadata_unavailable"

    if metadata.status.lower() != "open" or not metadata.trading_allowed:
        return 1, False, "metadata_unavailable"

    if not metadata.contracts or not any(
        c.status.lower() == "open" and c.tradable for c in metadata.contracts
    ):
        return 1, False, "metadata_unavailable"

    if (
        not isinstance(metadata.min_price_cents, int)
        or not isinstance(metadata.max_price_cents, int)
        or not isinstance(metadata.tick_size_cents, int)
        or metadata.tick_size_cents < 1
        or metadata.min_price_cents < 1
        or metadata.max_price_cents > 99
        or metadata.min_price_cents > metadata.max_price_cents
    ):
        return 1, False, "metadata_unavailable"

    price = metadata.min_price_cents
    if price > metadata.max_price_cents:
        return 1, False, "metadata_unavailable"

    return price, True, "metadata_min_price"


class ReadOnlyDiscoveryError(Exception):
    """Raised when read-only discovery is blocked by auth/network/API issues."""

    def __init__(self, blocker: str, cause: Exception | None = None):
        self.blocker = blocker
        self.cause = cause
        super().__init__(blocker)


def _classify_discovery_exception(exc: Exception) -> str:
    """Map an exception to a safe, precise blocker string."""
    name = type(exc).__name__
    text = str(exc).lower()
    if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text:
        return "AUTH_OR_NETWORK_BLOCKED"
    if "404" in text or "not found" in text:
        return "MARKET_METADATA_UNAVAILABLE"
    if "timeout" in text or name.lower().startswith("timeout"):
        return "AUTH_OR_NETWORK_BLOCKED"
    if "connect" in text or "network" in text or "dns" in text:
        return "AUTH_OR_NETWORK_BLOCKED"
    if name in {"HTTPStatusError"}:
        return "AUTH_OR_NETWORK_BLOCKED"
    return f"READ_ONLY_METADATA_EXCEPTION:{name}"


async def discover_live_eligible_candidates(
    client: Any,
    max_candidates: int = 10,
    prefer_event: str | None = None,
) -> tuple[bool, MarketMetadata | None, str]:
    """Discover a live, tradable, low-risk market/contract candidate.

    Queries ``client.get_markets()``, filters for open/tradable markets with
    open contracts, derives a validated LIMIT price, and returns the lowest-
    risk candidate (smallest ``min_price_cents``) that is compatible with a
    single-contract LIMIT order.

    Returns:
        ``(True, metadata, "live_eligible_candidate_found")`` on success, or
        ``(False, None, <exact_blocker>)``.
    """
    try:
        raw = await client.get_markets()
    except Exception as exc:
        return False, None, _classify_discovery_exception(exc)

    markets = raw.get("markets", raw) if isinstance(raw, dict) else raw
    if not isinstance(markets, list):
        if markets is None and isinstance(raw, dict):
            return False, None, "RESPONSE_SCHEMA_UNSUPPORTED"
        return False, None, "RESPONSE_SCHEMA_UNSUPPORTED"

    if not markets:
        return False, None, "NO_MARKETS_RETURNED"

    candidates: list[MarketMetadata] = []
    skipped_reasons: list[str] = []
    for market in markets[:max_candidates]:
        metadata = _market_metadata_from_api(market)
        if metadata is None:
            skipped_reasons.append("UNPARSEABLE_MARKET")
            continue

        if prefer_event is not None:
            event_ticker = ""
            if isinstance(market, dict):
                event_ticker = str(market.get("event_ticker", "")).upper()
            if (
                prefer_event.upper() not in event_ticker
                and prefer_event.upper() not in metadata.ticker
            ):
                skipped_reasons.append(f"PREFER_EVENT_MISMATCH:{metadata.ticker}")
                continue

        if metadata.status != "open" or not metadata.trading_allowed:
            skipped_reasons.append(f"MARKET_NOT_OPEN:{metadata.ticker}:{metadata.status}")
            continue
        if not any(c.status == "open" and c.tradable for c in metadata.contracts):
            skipped_reasons.append(f"NO_TRADABLE_CONTRACT:{metadata.ticker}")
            continue

        price, validated, _ = derive_validated_price(metadata)
        if not validated:
            skipped_reasons.append(f"NO_VALID_LIMIT_PRICE:{metadata.ticker}")
            continue

        sample_payload = {
            "ticker": metadata.ticker,
            "side": "yes",
            "action": "buy",
            "type": "LIMIT",
            "count": 1,
            "price": price,
            "client_order_id": "discovery-sample",
        }
        if not validate_order_payload_shape(sample_payload).ok:
            skipped_reasons.append(f"PAYLOAD_SHAPE_REJECTED:{metadata.ticker}")
            continue
        if not validate_payload_against_metadata(sample_payload, metadata).ok:
            skipped_reasons.append(f"PAYLOAD_METADATA_REJECTED:{metadata.ticker}")
            continue

        candidates.append(metadata)

    if not candidates:
        # Return the most specific blocker we can infer from skipped markets.
        if any("NO_VALID_LIMIT_PRICE" in r for r in skipped_reasons):
            return False, None, "NO_VALID_LIMIT_PRICE"
        if any("NO_TRADABLE_CONTRACT" in r for r in skipped_reasons):
            return False, None, "NO_TRADABLE_CONTRACTS"
        if any("MARKET_NOT_OPEN" in r for r in skipped_reasons):
            return False, None, "NO_TRADABLE_MARKETS"
        return False, None, "NO_LIVE_ELIGIBLE_CANDIDATE_FOUND"

    candidates.sort(key=lambda m: (m.min_price_cents, m.tick_size_cents))
    return True, candidates[0], "live_eligible_candidate_found"
