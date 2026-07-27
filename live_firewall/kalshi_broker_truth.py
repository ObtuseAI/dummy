"""Credential-owned, read-only Kalshi broker-truth projection for DumbMoney.

The provider is intentionally narrower than the general Kalshi client.  It
uses an injected RSA credential directly, pins the production origin and v2
path, ignores ambient proxy configuration, performs no retries, and exposes
only a conservative reconciliation snapshot.  No order mutation method exists
in this module.
"""

from __future__ import annotations

import base64
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from kalshi.strict_json import load_strict_json_response
from live_firewall.operational_journal import canonical_json, sha256_json


KALSHI_PRODUCTION_ORIGIN = "https://external-api.kalshi.com"
KALSHI_API_PREFIX = "/trade-api/v2"
MAXIMUM_RESPONSE_BYTES = 8 * 1024 * 1024
MAXIMUM_PAGES = 64
MAXIMUM_RECORDS = 64_000
REQUEST_TIMEOUT_SECONDS = 10.0

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,255}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,255}$")
_FIXED_POINT_RE = re.compile(
    r"^-?(?:0|[1-9][0-9]{0,18})(?:\.[0-9]{1,6})?$"
)


class KalshiBrokerTruthError(RuntimeError):
    """The authenticated broker snapshot could not be proven complete."""


@dataclass(frozen=True)
class _BufferedResponse:
    content: bytes


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KalshiBrokerTruthError(f"{field} must be an object")
    return value


def _list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise KalshiBrokerTruthError(f"{field} must be an array")
    return value


def _integer(
    value: Any,
    *,
    field: str,
    minimum: int = 0,
    maximum: int = 2**63 - 1,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise KalshiBrokerTruthError(f"{field} is outside its integer domain")
    return value


def _identifier(value: Any, *, field: str, ticker: bool = False) -> str:
    pattern = _TICKER_RE if ticker else _IDENTIFIER_RE
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise KalshiBrokerTruthError(f"{field} is invalid")
    return value


def _cursor(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 4_096
        or any(ord(character) < 0x20 for character in value)
    ):
        raise KalshiBrokerTruthError(f"{field} is invalid")
    return value


def _fixed_point(
    value: Any,
    *,
    field: str,
    allow_negative: bool,
) -> Decimal:
    if not isinstance(value, str) or not _FIXED_POINT_RE.fullmatch(value):
        raise KalshiBrokerTruthError(f"{field} is not a fixed-point string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise KalshiBrokerTruthError(f"{field} is invalid") from exc
    if not parsed.is_finite() or (not allow_negative and parsed < 0):
        raise KalshiBrokerTruthError(f"{field} is outside its numeric domain")
    if parsed.copy_abs() > Decimal("1000000000000000"):
        raise KalshiBrokerTruthError(f"{field} exceeds the sealed maximum")
    return parsed


def _dollars_to_conservative_cents(value: Decimal, *, field: str) -> int:
    cents = int(
        (value.copy_abs() * Decimal(100)).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    return _integer(cents, field=field)


def _whole_count(value: Any, *, field: str) -> int:
    parsed = _fixed_point(value, field=field, allow_negative=False)
    if parsed != parsed.to_integral_value():
        raise KalshiBrokerTruthError(
            f"{field} is fractional for a whole-contract DumbMoney order"
        )
    return _integer(int(parsed), field=field)


def _parse_utc_text(value: Any, *, field: str) -> datetime:
    if (
        not isinstance(value, str)
        or not value.endswith("Z")
        or len(value) > 64
    ):
        raise KalshiBrokerTruthError(f"{field} is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise KalshiBrokerTruthError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KalshiBrokerTruthError(f"{field} is timezone-naive")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    rendered = value.astimezone(timezone.utc).isoformat(
        timespec="microseconds" if value.microsecond else "seconds"
    )
    return rendered.replace("+00:00", "Z")


class KalshiBrokerTruthProvider:
    """Build a stable, fully paginated projection of one Kalshi subaccount."""

    def __init__(
        self,
        *,
        api_key_id: str,
        private_key_pem: bytes,
        expected_account_hash: str,
        subaccount_number: int,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        maximum_pages: int = MAXIMUM_PAGES,
        maximum_records: int = MAXIMUM_RECORDS,
    ) -> None:
        if not isinstance(api_key_id, str) or not _KEY_ID_RE.fullmatch(
            api_key_id
        ):
            raise KalshiBrokerTruthError("Kalshi API key id is invalid")
        if not isinstance(private_key_pem, bytes):
            raise KalshiBrokerTruthError("Kalshi private key must be bytes")
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=None,
            )
        except (TypeError, ValueError) as exc:
            raise KalshiBrokerTruthError(
                "Kalshi private key is invalid"
            ) from exc
        if (
            not isinstance(private_key, RSAPrivateKey)
            or private_key.key_size < 2_048
        ):
            raise KalshiBrokerTruthError(
                "Kalshi private key must be RSA with at least 2048 bits"
            )
        if (
            not isinstance(expected_account_hash, str)
            or not _SHA256_RE.fullmatch(expected_account_hash)
        ):
            raise KalshiBrokerTruthError("expected account hash is invalid")
        if (
            isinstance(subaccount_number, bool)
            or not isinstance(subaccount_number, int)
            or subaccount_number != 0
        ):
            raise KalshiBrokerTruthError(
                "only the sealed primary Kalshi subaccount is supported"
            )
        binding_hash = sha256_json(
            {
                "schema": "dummy.kalshi-account-binding.v1",
                "venue": "dummy_kalshi",
                "api_key_id": api_key_id,
                "subaccount_number": subaccount_number,
            }
        )
        if binding_hash != expected_account_hash:
            raise KalshiBrokerTruthError(
                "Kalshi key and subaccount do not match the account pin"
            )
        if (
            isinstance(maximum_pages, bool)
            or not isinstance(maximum_pages, int)
            or not 1 <= maximum_pages <= MAXIMUM_PAGES
        ):
            raise KalshiBrokerTruthError("maximum_pages is invalid")
        if (
            isinstance(maximum_records, bool)
            or not isinstance(maximum_records, int)
            or not 1 <= maximum_records <= MAXIMUM_RECORDS
        ):
            raise KalshiBrokerTruthError("maximum_records is invalid")

        self._api_key_id = api_key_id
        self._private_key = private_key
        self._expected_account_hash = expected_account_hash
        self._subaccount_number = subaccount_number
        self._clock = clock
        self._maximum_pages = maximum_pages
        self._maximum_records = maximum_records
        self._lock = threading.Lock()
        self._client = client or httpx.Client(
            base_url=f"{KALSHI_PRODUCTION_ORIGIN}{KALSHI_API_PREFIX}/",
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=1,
                max_keepalive_connections=1,
            ),
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KalshiBrokerTruthError(
                "broker-truth clock must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    def _headers(self, endpoint_path: str) -> dict[str, str]:
        timestamp = str(int(self._now().timestamp() * 1_000))
        signed_path = f"{KALSHI_API_PREFIX}/{endpoint_path.lstrip('/')}"
        message = f"{timestamp}GET{signed_path}".encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {
            "Accept": "application/json",
            "KALSHI-ACCESS-KEY": self._api_key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(
                "ascii"
            ),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def _request(
        self,
        endpoint_path: str,
        *,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if endpoint_path not in {
            "historical/fills",
            "historical/orders",
            "portfolio/balance",
            "portfolio/fills",
            "portfolio/positions",
            "portfolio/orders",
            "portfolio/settlements",
        }:
            raise KalshiBrokerTruthError("broker-truth endpoint is not allowed")
        try:
            with self._client.stream(
                "GET",
                endpoint_path,
                params=dict(params),
                headers=self._headers(endpoint_path),
            ) as response:
                response_url = response.request.url
                expected_path = (
                    f"{KALSHI_API_PREFIX}/{endpoint_path.lstrip('/')}"
                )
                if (
                    response_url.scheme != "https"
                    or response_url.host != "external-api.kalshi.com"
                    or response_url.port not in {None, 443}
                    or response_url.path != expected_path
                ):
                    raise KalshiBrokerTruthError(
                        "Kalshi response origin or path is not sealed"
                    )
                length_header = response.headers.get("content-length")
                if length_header is not None:
                    try:
                        content_length = int(length_header)
                    except ValueError as exc:
                        raise KalshiBrokerTruthError(
                            "Kalshi Content-Length is invalid"
                        ) from exc
                    if (
                        content_length < 0
                        or content_length > MAXIMUM_RESPONSE_BYTES
                    ):
                        raise KalshiBrokerTruthError(
                            "Kalshi response exceeds the byte limit"
                        )
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAXIMUM_RESPONSE_BYTES:
                        raise KalshiBrokerTruthError(
                            "Kalshi response exceeds the byte limit"
                        )
                if response.status_code != 200:
                    raise KalshiBrokerTruthError(
                        "Kalshi read failed with "
                        f"HTTP status {response.status_code}"
                    )
        except KalshiBrokerTruthError:
            raise
        except (httpx.HTTPError, OSError) as exc:
            raise KalshiBrokerTruthError(
                "Kalshi read transport failed"
            ) from exc
        try:
            payload = load_strict_json_response(
                _BufferedResponse(bytes(body)),
                maximum_bytes=MAXIMUM_RESPONSE_BYTES,
            )
        except (TypeError, ValueError) as exc:
            raise KalshiBrokerTruthError(
                "Kalshi read response is not strict bounded JSON"
            ) from exc
        return _mapping(payload, field=f"Kalshi {endpoint_path} response")

    def _balance(self) -> dict[str, int | str]:
        payload = self._request(
            "portfolio/balance",
            params={"subaccount": self._subaccount_number},
        )
        balance = _integer(payload.get("balance"), field="balance")
        portfolio_value = _integer(
            payload.get("portfolio_value"),
            field="portfolio_value",
        )
        updated_ts = _integer(
            payload.get("updated_ts"),
            field="updated_ts",
        )
        balance_dollars = _fixed_point(
            payload.get("balance_dollars"),
            field="balance_dollars",
            allow_negative=False,
        )
        if balance_dollars * Decimal(100) != Decimal(balance):
            raise KalshiBrokerTruthError(
                "balance cents and fixed-point dollars disagree"
            )
        return {
            "balance_cents": balance,
            "balance_dollars": str(balance_dollars),
            "portfolio_value_cents": portfolio_value,
            "updated_ts": updated_ts,
        }

    def _positions(self) -> dict[str, list[dict[str, Any]]]:
        market_positions: list[dict[str, Any]] = []
        event_positions: list[dict[str, Any]] = []
        seen_market: set[str] = set()
        seen_event: set[str] = set()
        seen_cursors: set[str] = set()
        cursor = ""

        for _page in range(self._maximum_pages):
            params: dict[str, Any] = {
                "limit": 1_000,
                "count_filter": "position",
                "subaccount": self._subaccount_number,
            }
            if cursor:
                params["cursor"] = cursor
            payload = self._request("portfolio/positions", params=params)
            markets = _list(
                payload.get("market_positions"),
                field="market_positions",
            )
            events = _list(
                payload.get("event_positions"),
                field="event_positions",
            )
            for index, raw in enumerate(markets):
                item = _mapping(
                    raw,
                    field=f"market_positions[{index}]",
                )
                ticker = _identifier(
                    item.get("ticker"),
                    field="market position ticker",
                    ticker=True,
                )
                if ticker in seen_market:
                    raise KalshiBrokerTruthError(
                        "market position ticker is duplicated"
                    )
                seen_market.add(ticker)
                position = _fixed_point(
                    item.get("position_fp"),
                    field=f"{ticker}.position_fp",
                    allow_negative=True,
                )
                if position == 0:
                    raise KalshiBrokerTruthError(
                        "position-filtered response contains a zero position"
                    )
                exposure = _fixed_point(
                    item.get("market_exposure_dollars"),
                    field=f"{ticker}.market_exposure_dollars",
                    allow_negative=True,
                )
                updated = item.get("last_updated_ts")
                if (
                    not isinstance(updated, str)
                    or not updated.endswith("Z")
                    or len(updated) > 64
                ):
                    raise KalshiBrokerTruthError(
                        "market position timestamp is invalid"
                    )
                try:
                    parsed_updated = datetime.fromisoformat(
                        updated[:-1] + "+00:00"
                    )
                except ValueError as exc:
                    raise KalshiBrokerTruthError(
                        "market position timestamp is invalid"
                    ) from exc
                if (
                    parsed_updated.tzinfo is None
                    or parsed_updated.utcoffset() is None
                ):
                    raise KalshiBrokerTruthError(
                        "market position timestamp is naive"
                    )
                if parsed_updated > self._now() + timedelta(seconds=5):
                    raise KalshiBrokerTruthError(
                        "market position timestamp is in the future"
                    )
                market_positions.append(
                    {
                        "ticker": ticker,
                        "position_fp": str(position),
                        "market_exposure_cents": (
                            _dollars_to_conservative_cents(
                                exposure,
                                field=f"{ticker}.market_exposure_cents",
                            )
                        ),
                        "last_updated_ts": _format_utc(parsed_updated),
                    }
                )
            for index, raw in enumerate(events):
                item = _mapping(
                    raw,
                    field=f"event_positions[{index}]",
                )
                event_ticker = _identifier(
                    item.get("event_ticker"),
                    field="event position ticker",
                    ticker=True,
                )
                if event_ticker in seen_event:
                    raise KalshiBrokerTruthError(
                        "event position ticker is duplicated"
                    )
                seen_event.add(event_ticker)
                exposure = _fixed_point(
                    item.get("event_exposure_dollars"),
                    field=f"{event_ticker}.event_exposure_dollars",
                    allow_negative=True,
                )
                event_positions.append(
                    {
                        "event_ticker": event_ticker,
                        "event_exposure_cents": (
                            _dollars_to_conservative_cents(
                                exposure,
                                field=(
                                    f"{event_ticker}.event_exposure_cents"
                                ),
                            )
                        ),
                    }
                )
            if (
                len(market_positions) + len(event_positions)
                > self._maximum_records
            ):
                raise KalshiBrokerTruthError(
                    "position snapshot exceeds the record limit"
                )
            next_cursor = _cursor(
                payload.get("cursor"),
                field="positions cursor",
            )
            if not next_cursor:
                market_positions.sort(key=lambda item: item["ticker"])
                event_positions.sort(key=lambda item: item["event_ticker"])
                return {
                    "market_positions": market_positions,
                    "event_positions": event_positions,
                }
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise KalshiBrokerTruthError(
                    "positions cursor repeated"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise KalshiBrokerTruthError("positions pagination is incomplete")

    def _orders(self) -> list[dict[str, Any]]:
        orders: list[dict[str, Any]] = []
        seen_orders: set[str] = set()
        seen_cursors: set[str] = set()
        cursor = ""

        for _page in range(self._maximum_pages):
            params: dict[str, Any] = {
                "status": "resting",
                "limit": 1_000,
                "subaccount": self._subaccount_number,
            }
            if cursor:
                params["cursor"] = cursor
            payload = self._request("portfolio/orders", params=params)
            page_orders = _list(payload.get("orders"), field="orders")
            for index, raw in enumerate(page_orders):
                item = _mapping(raw, field=f"orders[{index}]")
                order_id = _identifier(
                    item.get("order_id"),
                    field="order_id",
                )
                if order_id in seen_orders:
                    raise KalshiBrokerTruthError("order_id is duplicated")
                seen_orders.add(order_id)
                ticker = _identifier(
                    item.get("ticker"),
                    field=f"{order_id}.ticker",
                    ticker=True,
                )
                subaccount = _integer(
                    item.get("subaccount_number"),
                    field=f"{order_id}.subaccount_number",
                    maximum=63,
                )
                if subaccount != self._subaccount_number:
                    raise KalshiBrokerTruthError(
                        "order belongs to a different subaccount"
                    )
                remaining = _fixed_point(
                    item.get("remaining_count_fp"),
                    field=f"{order_id}.remaining_count_fp",
                    allow_negative=False,
                )
                if remaining <= 0:
                    raise KalshiBrokerTruthError(
                        "resting order has no remaining count"
                    )
                yes_price = _fixed_point(
                    item.get("yes_price_dollars"),
                    field=f"{order_id}.yes_price_dollars",
                    allow_negative=False,
                )
                no_price = _fixed_point(
                    item.get("no_price_dollars"),
                    field=f"{order_id}.no_price_dollars",
                    allow_negative=False,
                )
                if (
                    yes_price > 1
                    or no_price > 1
                    or yes_price + no_price != 1
                ):
                    raise KalshiBrokerTruthError(
                        "order price pair is inconsistent"
                    )
                orders.append(
                    {
                        "order_id": order_id,
                        "ticker": ticker,
                        "subaccount_number": subaccount,
                        "remaining_count_fp": str(remaining),
                        "yes_price_dollars": str(yes_price),
                        "no_price_dollars": str(no_price),
                    }
                )
            if len(orders) > self._maximum_records:
                raise KalshiBrokerTruthError(
                    "order snapshot exceeds the record limit"
                )
            next_cursor = _cursor(
                payload.get("cursor"),
                field="orders cursor",
            )
            if not next_cursor:
                orders.sort(key=lambda item: item["order_id"])
                return orders
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise KalshiBrokerTruthError("orders cursor repeated")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise KalshiBrokerTruthError("orders pagination is incomplete")

    def _stable_state(self) -> dict[str, Any]:
        return {
            "positions": self._positions(),
            "resting_orders": self._orders(),
        }

    def snapshot(self) -> Mapping[str, Any]:
        """Return one stable account-scoped truth projection or fail closed."""
        if not self._lock.acquire(blocking=False):
            raise KalshiBrokerTruthError(
                "a broker-truth snapshot is already in progress"
            )
        try:
            balance = self._balance()
            first_state = self._stable_state()
            second_state = self._stable_state()
            if canonical_json(first_state) != canonical_json(second_state):
                raise KalshiBrokerTruthError(
                    "Kalshi positions or orders changed during reconciliation"
                )
            observed_at = self._now()
            market_positions = first_state["positions"]["market_positions"]
            event_positions = first_state["positions"]["event_positions"]
            resting_orders = first_state["resting_orders"]
            if event_positions and not market_positions:
                raise KalshiBrokerTruthError(
                    "event exposure exists without a market position"
                )
            market_exposure = {
                item["ticker"]: item["market_exposure_cents"]
                for item in market_positions
            }
            correlated_exposure = {
                item["event_ticker"]: item["event_exposure_cents"]
                for item in event_positions
            }
            market_total = sum(market_exposure.values())
            correlated_total = sum(correlated_exposure.values())
            total_exposure = max(market_total, correlated_total)
            if market_positions and not correlated_exposure:
                correlated_exposure = {
                    "ACCOUNT_WIDE_UNGROUPED": total_exposure
                }
            flat = (
                not market_positions
                and not resting_orders
                and total_exposure == 0
            )
            digest_payload = {
                "schema": "dummy.kalshi-broker-raw-snapshot.v1",
                "venue": "dummy_kalshi",
                "account_hash": self._expected_account_hash,
                "subaccount_number": self._subaccount_number,
                "observed_at": _format_utc(observed_at),
                "balance": balance,
                "state": first_state,
            }
            return {
                "schema": "dummy.kalshi-broker-truth.v1",
                "venue": "dummy_kalshi",
                "account_hash": self._expected_account_hash,
                "subaccount_number": self._subaccount_number,
                "observed_at": digest_payload["observed_at"],
                "broker_snapshot_sha256": sha256_json(digest_payload),
                "flat_book_observed": flat,
                "total_exposure_cents": total_exposure,
                "open_order_count": len(resting_orders),
                "market_exposure_cents": market_exposure,
                "correlated_exposure_cents": correlated_exposure,
                "unresolved_open_orders": len(resting_orders),
                "unresolved_positions": len(market_positions),
            }
        finally:
            self._lock.release()

    def close(self) -> None:
        self._client.close()


__all__ = [
    "KALSHI_API_PREFIX",
    "KALSHI_PRODUCTION_ORIGIN",
    "KalshiBrokerTruthError",
    "KalshiBrokerTruthProvider",
]
