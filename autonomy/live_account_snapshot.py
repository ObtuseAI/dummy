"""Sanitized, authenticated, GET-only Kalshi account snapshot.

This module is deliberately separate from execution.  It has no order-submit,
session, cap, or live-mode configuration path.  The production collector wraps
the Kalshi HTTP transport with an exact GET/path allowlist and then persists
only account-level balances and aggregate counts.  Identifiers and raw broker
responses never cross the artifact boundary.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import httpx

from core.env_loader import (
    KALSHI_ENV_REFS,
    apply_whitelisted_env,
    read_whitelisted_env,
)


LIVE_ACCOUNT_SNAPSHOT_SCHEMA = "dummy.live_account_snapshot"
LIVE_ACCOUNT_SNAPSHOT_VERSION = 1
LIVE_ACCOUNT_SNAPSHOT_PATH = Path("runtime/autonomy/live_account_snapshot.json")
LIVE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS = 600
LIVE_ACCOUNT_SNAPSHOT_MAX_PAGES = 2
LIVE_ACCOUNT_SNAPSHOT_PAGE_LIMIT = 1000

_ALLOWED_PATHS = frozenset(
    {
        "/portfolio/balance",
        "/portfolio/positions",
        "/portfolio/orders",
        "/portfolio/fills",
    }
)
_ALLOWED_KALSHI_HOSTS = frozenset(
    {
        "api.elections.kalshi.com",
        "external-api.kalshi.com",
    }
)
_REQUIRED_PATHS = frozenset(
    {
        "/portfolio/balance",
        "/portfolio/positions",
        "/portfolio/orders",
    }
)
_OPEN_ORDER_STATUSES = frozenset({"resting", "pending", "open"})
_KNOWN_ORDER_STATUSES = frozenset(
    {"resting", "pending", "open", "canceled", "executed"}
)
_SAFE_HTTP_METHODS = frozenset(
    {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
)
_SAFE_STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx"})
_SAFE_REASONS = frozenset(
    {
        None,
        "artifact_age_exceeded",
        "client_audit_violation",
        "invalid_endpoint_configuration",
        "missing_credentials",
        "optional_fills_truncated",
        "optional_fills_unavailable",
        "required_pagination_truncated",
        "source_error",
    }
)
_SAFE_ERROR_STAGES = frozenset(
    {"credentials", "balance", "positions", "orders", "fills", "http_audit"}
)
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "version",
        "generated_at",
        "status",
        "stale",
        "reason",
        "execution_authority",
        "balance_cents",
        "available_balance_cents",
        "open_positions_count",
        "open_orders_count",
        "historical_orders_count",
        "historical_fills_count",
        "order_status_counts",
        "optional_fills_status",
        "counts_are_lower_bounds",
        "pagination",
        "source",
        "http_proof",
        "errors",
    }
)


class AccountSnapshotSourceShapeError(RuntimeError):
    """A required Kalshi response was not countable without guessing."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime:
    value = value or _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_collection_path(path: str) -> str:
    raw = urlsplit(str(path)).path.replace("\\", "/")
    for _ in range(3):
        decoded = unquote(raw)
        if decoded == raw:
            break
        raw = decoded
    segments: list[str] = []
    for part in raw.split("/"):
        normalized = part.strip()
        if not normalized or normalized == ".":
            continue
        if normalized == "..":
            if segments:
                segments.pop()
            continue
        segments.append(normalized.casefold())
    return "/" + "/".join(segments)


def _is_allowed_relative_path(path: str) -> bool:
    parsed = urlsplit(str(path).replace("\\", "/"))
    return (
        not parsed.scheme
        and not parsed.netloc
        and _canonical_collection_path(path) in _ALLOWED_PATHS
    )


class AccountSnapshotGetOnlyTransport:
    """Exact GET-only, collection-path-only wrapper for the snapshot process."""

    def __init__(self, client: Any):
        self.client = client
        self.blocked_attempts: list[dict[str, str]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        normalized_method = str(method).strip().upper()
        if normalized_method != "GET":
            self.blocked_attempts.append(
                {"kind": "method", "method": _safe_method(normalized_method)}
            )
            raise PermissionError("GET_ONLY_TRANSPORT_BLOCKED_METHOD")
        if not _is_allowed_relative_path(path):
            self.blocked_attempts.append({"kind": "path", "method": "GET"})
            raise PermissionError("GET_ONLY_TRANSPORT_BLOCKED_PATH")
        # KalshiClient supplies ``content=b""`` for every signed request.  An
        # empty body is safe; any material GET payload or alternate body
        # channel is not.
        content = kwargs.get("content")
        has_material_content = content not in (None, "", b"")
        has_alternate_body = any(name in kwargs for name in ("data", "files", "json"))
        if has_material_content or has_alternate_body:
            self.blocked_attempts.append({"kind": "payload", "method": "GET"})
            raise PermissionError("GET_ONLY_TRANSPORT_BLOCKED_PAYLOAD")
        return await self.client.request("GET", path, **kwargs)

    async def aclose(self) -> None:
        close = getattr(self.client, "aclose", None)
        if close is not None:
            await close()


def load_live_account_env(dotenv_path: Path | str = Path(".env")) -> dict[str, str]:
    """Load only Kalshi credential references from the project dotenv file."""
    values = read_whitelisted_env(dotenv_path=dotenv_path)
    kalshi_only = {key: value for key, value in values.items() if key in KALSHI_ENV_REFS}
    return apply_whitelisted_env(kalshi_only, overwrite=False)


def _credential_configuration_error() -> str | None:
    key_id = bool(os.environ.get("KALSHI_API_KEY_ID"))
    inline_key = bool(
        os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
        or os.environ.get("KALSHI_API_PRIVATE_KEY")
    )
    path_value = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
    path_ready = bool(path_value and Path(path_value).is_file())
    if not key_id or not (inline_key or path_ready):
        return "CREDENTIALS_MISSING"

    base = os.environ.get(
        "KALSHI_API_BASE",
        "https://api.elections.kalshi.com",
    ).strip()
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError:
        return "INVALID_KALSHI_ENDPOINT"
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() not in _ALLOWED_KALSHI_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        return "INVALID_KALSHI_ENDPOINT"
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    if version != "trade-api/v2":
        return "INVALID_KALSHI_ENDPOINT"
    return None


def _safe_method(value: Any) -> str:
    method = str(value or "").strip().upper()
    return method if method in _SAFE_HTTP_METHODS else "OTHER"


def _safe_status_class(value: Any) -> str:
    status_class = str(value or "").strip().casefold()
    return status_class if status_class in _SAFE_STATUS_CLASSES else "unknown"


def _transport_guard(client: Any) -> AccountSnapshotGetOnlyTransport | None:
    raw_transport = getattr(client, "client", None)
    if raw_transport is None:
        return None
    if isinstance(raw_transport, AccountSnapshotGetOnlyTransport):
        return raw_transport
    guard = AccountSnapshotGetOnlyTransport(raw_transport)
    client.client = guard
    return guard


def _request_audit(client: Any) -> tuple[list[Mapping[str, Any]], int]:
    raw = getattr(client, "request_audit_log", ())
    try:
        entries = list(raw)
    except TypeError:
        return [], 1
    valid = [entry for entry in entries if isinstance(entry, Mapping)]
    return valid, len(entries) - len(valid)


def _http_proof(
    client: Any,
    guard: AccountSnapshotGetOnlyTransport | None,
) -> dict[str, Any]:
    audit, invalid_audit_entries = _request_audit(client)
    method_counts: Counter[str] = Counter()
    endpoint_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    mutation_count = 0
    unexpected_path_count = invalid_audit_entries

    for entry in audit:
        method = _safe_method(entry.get("method"))
        method_counts[method] += 1
        if method != "GET":
            mutation_count += 1
        candidate_path = entry.get("path_family", entry.get("path", ""))
        candidate_path = str(candidate_path)
        path = _canonical_collection_path(candidate_path)
        if _is_allowed_relative_path(candidate_path):
            endpoint_counts[path] += 1
        else:
            unexpected_path_count += 1
        status_counts[_safe_status_class(entry.get("status_class"))] += 1

    blocked = list(getattr(guard, "blocked_attempts", ())) if guard else []
    mutation_count += sum(item.get("kind") != "path" for item in blocked)
    unexpected_path_count += sum(item.get("kind") == "path" for item in blocked)
    audit_valid = mutation_count == 0 and unexpected_path_count == 0
    return {
        "get_only": audit_valid and set(method_counts).issubset({"GET"}),
        "audit_valid": audit_valid,
        "total_requests": len(audit) + invalid_audit_entries,
        "methods": sorted(method_counts),
        "path_families": sorted(endpoint_counts),
        "endpoint_request_counts": dict(sorted(endpoint_counts.items())),
        "status_classes": sorted(status_counts),
        "mutation_count": mutation_count,
        "unexpected_path_count": unexpected_path_count,
        "blocked_attempt_count": len(blocked),
    }


def _audit_has_violation(proof: Mapping[str, Any]) -> bool:
    return not bool(proof.get("audit_valid")) or not bool(proof.get("get_only"))


def _required_audit_complete(proof: Mapping[str, Any]) -> bool:
    observed_paths = set(proof.get("path_families", ()))
    return (
        not _audit_has_violation(proof)
        and _REQUIRED_PATHS.issubset(observed_paths)
        and int(proof.get("total_requests") or 0) >= len(_REQUIRED_PATHS)
        and "2xx" in proof.get("status_classes", ())
    )


def _source(*, authenticated: bool) -> dict[str, Any]:
    return {
        "provider": "kalshi",
        "authenticated": authenticated,
        "data_class": "live_account_read_only",
        # Kalshi moves older completed orders/fills behind separate historical
        # endpoints.  This writer intentionally does not expand its allowlist.
        "history_scope": "live_portfolio_retention_window",
    }


def _empty_snapshot(
    *,
    generated_at: datetime,
    status: str,
    stale: bool,
    reason: str,
    proof: Mapping[str, Any],
    errors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    authenticated = "2xx" in proof.get("status_classes", ())
    return {
        "schema": LIVE_ACCOUNT_SNAPSHOT_SCHEMA,
        "version": LIVE_ACCOUNT_SNAPSHOT_VERSION,
        "generated_at": generated_at.isoformat(),
        "status": status,
        "stale": stale,
        "reason": reason,
        "execution_authority": False,
        "balance_cents": None,
        "open_positions_count": None,
        "open_orders_count": None,
        "historical_orders_count": None,
        "order_status_counts": {},
        "optional_fills_status": "NOT_COLLECTED",
        "counts_are_lower_bounds": False,
        "pagination": {},
        "source": _source(authenticated=authenticated),
        "http_proof": dict(proof),
        "errors": [dict(error) for error in errors],
    }


def _safe_error(stage: str, exc: BaseException) -> dict[str, Any]:
    code = "SOURCE_ERROR"
    retryable = False
    if isinstance(exc, httpx.HTTPStatusError):
        code = f"HTTP_{int(exc.response.status_code)}"
        retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
    elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        code = "TIMEOUT"
        retryable = True
    elif isinstance(exc, httpx.NetworkError):
        code = "NETWORK_ERROR"
        retryable = True
    elif isinstance(exc, AccountSnapshotSourceShapeError):
        code = "SOURCE_SHAPE_ERROR"
    elif isinstance(exc, PermissionError):
        code = "TRANSPORT_GUARD_BLOCKED"
    elif isinstance(exc, RuntimeError):
        code = "RUNTIME_ERROR"
    return {"stage": stage, "code": code, "retryable": retryable}


async def _get(client: Any, path: str, **params: Any) -> dict[str, Any]:
    if path not in _ALLOWED_PATHS:
        raise PermissionError("GET_ONLY_COLLECTOR_BLOCKED_PATH")
    response = await client._request("GET", path, params=params or None)
    if not isinstance(response, dict):
        raise AccountSnapshotSourceShapeError("required response is not an object")
    return response


async def _paginate(
    client: Any,
    *,
    path: str,
    item_keys: Sequence[str],
    max_pages: int,
    base_params: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int, bool]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0
    truncated = False

    for _ in range(max(1, max_pages)):
        params = dict(base_params or {})
        params["limit"] = LIVE_ACCOUNT_SNAPSHOT_PAGE_LIMIT
        if cursor:
            params["cursor"] = cursor
        page = await _get(client, path, **params)
        pages += 1
        page_items: Any = None
        for key in item_keys:
            if key in page:
                page_items = page[key]
                break
        if not isinstance(page_items, list):
            raise AccountSnapshotSourceShapeError("required list is unavailable")
        if len(page_items) > LIVE_ACCOUNT_SNAPSHOT_PAGE_LIMIT:
            raise AccountSnapshotSourceShapeError("source page exceeds requested limit")
        if not all(isinstance(item, dict) for item in page_items):
            raise AccountSnapshotSourceShapeError("required list contains invalid rows")
        items.extend(page_items)
        next_cursor = page.get("cursor")
        if not next_cursor:
            cursor = None
            break
        cursor = str(next_cursor)
        if len(cursor) > 4096:
            raise AccountSnapshotSourceShapeError("pagination cursor is oversized")
        if cursor in seen_cursors:
            raise AccountSnapshotSourceShapeError("pagination cursor repeated")
        seen_cursors.add(cursor)
    else:
        truncated = cursor is not None

    return items, pages, truncated


def _required_nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise AccountSnapshotSourceShapeError(f"{field} is not a nonnegative integer")
    return value


def _position_is_open(row: Mapping[str, Any]) -> bool:
    raw = row.get("position_fp", row.get("position"))
    if raw is None or isinstance(raw, bool):
        raise AccountSnapshotSourceShapeError("position quantity is unavailable")
    if isinstance(raw, str) and len(raw) > 64:
        raise AccountSnapshotSourceShapeError("position quantity is oversized")
    try:
        return Decimal(str(raw)) != 0
    except InvalidOperation as exc:
        raise AccountSnapshotSourceShapeError("position quantity is invalid") from exc


def _order_status_counts(orders: Sequence[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for order in orders:
        raw = str(order.get("status") or "").strip().casefold()
        counts[raw if raw in _KNOWN_ORDER_STATUSES else "other"] += 1
    return counts


def _audit_error_snapshot(
    generated_at: datetime,
    proof: Mapping[str, Any],
) -> dict[str, Any]:
    return _empty_snapshot(
        generated_at=generated_at,
        status="ERROR",
        stale=True,
        reason="client_audit_violation",
        proof=proof,
        errors=[
            {
                "stage": "http_audit",
                "code": "GET_ONLY_AUDIT_VIOLATION",
                "retryable": False,
            }
        ],
    )


async def collect_live_account_snapshot(
    *,
    client: Any,
    include_fills: bool = True,
    max_pages: int = LIVE_ACCOUNT_SNAPSHOT_MAX_PAGES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect aggregate account facts through the exact GET-only allowlist."""
    generated_at = _as_utc(now)
    try:
        bounded_max_pages = max(
            1,
            min(int(max_pages), LIVE_ACCOUNT_SNAPSHOT_MAX_PAGES),
        )
    except (TypeError, ValueError):
        bounded_max_pages = 1
    guard = _transport_guard(client)
    proof = _http_proof(client, guard)
    if _audit_has_violation(proof):
        return _audit_error_snapshot(generated_at, proof)

    optional_errors: list[dict[str, Any]] = []
    pagination: dict[str, int] = {}
    stage = "balance"
    try:
        balance = await _get(client, "/portfolio/balance")
        proof = _http_proof(client, guard)
        if _audit_has_violation(proof):
            return _audit_error_snapshot(generated_at, proof)

        stage = "positions"
        positions, position_pages, positions_truncated = await _paginate(
            client,
            path="/portfolio/positions",
            item_keys=("market_positions", "positions"),
            max_pages=bounded_max_pages,
            base_params={"count_filter": "position"},
        )
        proof = _http_proof(client, guard)
        if _audit_has_violation(proof):
            return _audit_error_snapshot(generated_at, proof)

        stage = "orders"
        orders, order_pages, orders_truncated = await _paginate(
            client,
            path="/portfolio/orders",
            item_keys=("orders",),
            max_pages=bounded_max_pages,
        )
        proof = _http_proof(client, guard)
        if _audit_has_violation(proof):
            return _audit_error_snapshot(generated_at, proof)
    except Exception as exc:
        proof = _http_proof(client, guard)
        if _audit_has_violation(proof):
            return _audit_error_snapshot(generated_at, proof)
        return _empty_snapshot(
            generated_at=generated_at,
            status="ERROR",
            stale=True,
            reason="source_error",
            proof=proof,
            errors=[_safe_error(stage, exc)],
        )

    pagination.update({"positions_pages": position_pages, "orders_pages": order_pages})
    required_truncated = positions_truncated or orders_truncated
    try:
        balance_cents = _required_nonnegative_int(balance.get("balance"), "balance")
        available_balance = balance.get("available_balance")
        if available_balance is not None:
            available_balance = _required_nonnegative_int(
                available_balance,
                "available_balance",
            )
    except AccountSnapshotSourceShapeError as exc:
        return _empty_snapshot(
            generated_at=generated_at,
            status="ERROR",
            stale=True,
            reason="source_error",
            proof=proof,
            errors=[_safe_error("balance", exc)],
        )
    try:
        open_positions_count = sum(_position_is_open(row) for row in positions)
    except AccountSnapshotSourceShapeError as exc:
        return _empty_snapshot(
            generated_at=generated_at,
            status="ERROR",
            stale=True,
            reason="source_error",
            proof=proof,
            errors=[_safe_error("positions", exc)],
        )
    status_counts = _order_status_counts(orders)
    open_orders_count = sum(
        count for status, count in status_counts.items() if status in _OPEN_ORDER_STATUSES
    )
    historical_orders_count = len(orders) - open_orders_count

    historical_fills_count: int | None = None
    fills_truncated = False
    optional_fills_status = "NOT_REQUESTED"
    if include_fills:
        try:
            fills, fill_pages, fills_truncated = await _paginate(
                client,
                path="/portfolio/fills",
                item_keys=("fills",),
                max_pages=bounded_max_pages,
            )
            pagination["fills_pages"] = fill_pages
            historical_fills_count = len(fills)
            optional_fills_status = "TRUNCATED" if fills_truncated else "OK"
        except Exception as exc:
            optional_errors.append(_safe_error("fills", exc))
            optional_fills_status = "ERROR"

    proof = _http_proof(client, guard)
    if _audit_has_violation(proof):
        return _audit_error_snapshot(generated_at, proof)
    if not _required_audit_complete(proof):
        failed_proof = dict(proof)
        failed_proof["audit_valid"] = False
        return _audit_error_snapshot(generated_at, failed_proof)

    reason: str | None = None
    status = "FRESH"
    stale = False
    if required_truncated:
        status = "STALE"
        stale = True
        reason = "required_pagination_truncated"
    elif optional_fills_status == "ERROR":
        reason = "optional_fills_unavailable"
    elif fills_truncated:
        reason = "optional_fills_truncated"

    result: dict[str, Any] = {
        "schema": LIVE_ACCOUNT_SNAPSHOT_SCHEMA,
        "version": LIVE_ACCOUNT_SNAPSHOT_VERSION,
        "generated_at": generated_at.isoformat(),
        "status": status,
        "stale": stale,
        "reason": reason,
        "execution_authority": False,
        "balance_cents": balance_cents,
        "open_positions_count": open_positions_count,
        "open_orders_count": open_orders_count,
        "historical_orders_count": historical_orders_count,
        "order_status_counts": dict(sorted(status_counts.items())),
        "optional_fills_status": optional_fills_status,
        "counts_are_lower_bounds": required_truncated or fills_truncated,
        "pagination": pagination,
        "source": _source(authenticated="2xx" in proof.get("status_classes", ())),
        "http_proof": proof,
        "errors": optional_errors,
    }
    if available_balance is not None:
        result["available_balance_cents"] = available_balance
    if historical_fills_count is not None:
        result["historical_fills_count"] = historical_fills_count
    return result


def _safe_count(value: Any, *, nullable: bool) -> bool:
    return (nullable and value is None) or (type(value) is int and value >= 0)


def _parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_safe_errors(value: Any) -> bool:
    if not isinstance(value, list) or len(value) > 8:
        return False
    for item in value:
        if not isinstance(item, dict) or set(item) != {"stage", "code", "retryable"}:
            return False
        if not isinstance(item["stage"], str) or item["stage"] not in _SAFE_ERROR_STAGES:
            return False
        if not isinstance(item["code"], str) or not _SAFE_ERROR_CODE.fullmatch(item["code"]):
            return False
        if type(item["retryable"]) is not bool:
            return False
    return True


def _valid_source(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = {"provider", "authenticated", "data_class", "history_scope"}
    if not set(value).issubset(allowed):
        return False
    if value.get("provider") != "kalshi" or type(value.get("authenticated")) is not bool:
        return False
    if "data_class" in value and value["data_class"] != "live_account_read_only":
        return False
    if "history_scope" in value and value["history_scope"] != "live_portfolio_retention_window":
        return False
    return True


def _valid_http_proof(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = {
        "get_only",
        "audit_valid",
        "total_requests",
        "methods",
        "path_families",
        "endpoint_request_counts",
        "status_classes",
        "mutation_count",
        "unexpected_path_count",
        "blocked_attempt_count",
    }
    if not set(value).issubset(allowed) or type(value.get("get_only")) is not bool:
        return False
    for boolean_field in ("audit_valid",):
        if boolean_field in value and type(value[boolean_field]) is not bool:
            return False
    for count_field in (
        "total_requests",
        "mutation_count",
        "unexpected_path_count",
        "blocked_attempt_count",
    ):
        if count_field in value and not _safe_count(value[count_field], nullable=False):
            return False
    methods = value.get("methods", [])
    if not isinstance(methods, list) or not all(
        isinstance(method, str) and method in _SAFE_HTTP_METHODS | {"OTHER"}
        for method in methods
    ):
        return False
    paths = value.get("path_families", [])
    if not isinstance(paths, list) or not all(
        isinstance(path, str) and path in _ALLOWED_PATHS for path in paths
    ):
        return False
    statuses = value.get("status_classes", [])
    if not isinstance(statuses, list) or not all(
        isinstance(status, str) and status in _SAFE_STATUS_CLASSES | {"unknown"}
        for status in statuses
    ):
        return False
    endpoint_counts = value.get("endpoint_request_counts", {})
    if not isinstance(endpoint_counts, dict) or not set(endpoint_counts).issubset(
        _ALLOWED_PATHS
    ):
        return False
    return all(
        _safe_count(count, nullable=False) for count in endpoint_counts.values()
    )


def _valid_pagination(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not set(value).issubset({"positions_pages", "orders_pages", "fills_pages"}):
        return False
    return all(type(pages) is int and 1 <= pages <= LIVE_ACCOUNT_SNAPSHOT_MAX_PAGES for pages in value.values())


def _valid_contract(payload: Any, *, now: datetime | None = None) -> bool:
    if not isinstance(payload, dict) or not set(payload).issubset(_ALLOWED_TOP_LEVEL_KEYS):
        return False
    if payload.get("schema") != LIVE_ACCOUNT_SNAPSHOT_SCHEMA:
        return False
    if type(payload.get("version")) is not int or payload["version"] != 1:
        return False
    status = payload.get("status")
    if not isinstance(status, str) or status not in {"FRESH", "STALE", "ERROR"}:
        return False
    if type(payload.get("stale")) is not bool:
        return False
    if payload.get("status") == "FRESH" and payload["stale"] is not False:
        return False
    if payload.get("status") in {"STALE", "ERROR"} and payload["stale"] is not True:
        return False
    reason = payload.get("reason")
    if reason is not None and not isinstance(reason, str):
        return False
    if reason not in _SAFE_REASONS:
        return False
    if payload.get("execution_authority") is not False:
        return False
    generated_at = _parse_generated_at(payload.get("generated_at"))
    if generated_at is None:
        return False
    if now is not None and generated_at > _as_utc(now) + timedelta(minutes=5):
        return False

    nullable = payload.get("status") == "ERROR"
    for field in (
        "balance_cents",
        "open_positions_count",
        "open_orders_count",
        "historical_orders_count",
    ):
        if field not in payload or not _safe_count(payload[field], nullable=nullable):
            return False
    for optional_field in ("available_balance_cents", "historical_fills_count"):
        if optional_field in payload and not _safe_count(payload[optional_field], nullable=False):
            return False

    status_counts = payload.get("order_status_counts")
    if not isinstance(status_counts, dict) or not set(status_counts).issubset(
        _KNOWN_ORDER_STATUSES | {"other"}
    ):
        return False
    if not all(_safe_count(value, nullable=False) for value in status_counts.values()):
        return False
    if "optional_fills_status" in payload:
        fills_status = payload["optional_fills_status"]
        if not isinstance(fills_status, str) or fills_status not in {
            "NOT_COLLECTED",
            "NOT_REQUESTED",
            "OK",
            "TRUNCATED",
            "ERROR",
        }:
            return False
    if "counts_are_lower_bounds" in payload and type(payload["counts_are_lower_bounds"]) is not bool:
        return False
    if "pagination" in payload and not _valid_pagination(payload["pagination"]):
        return False
    if not _valid_source(payload.get("source")):
        return False
    proof = payload.get("http_proof")
    if not _valid_http_proof(proof):
        return False
    if payload.get("status") == "FRESH" and proof.get("get_only") is not True:
        return False
    return _valid_safe_errors(payload.get("errors"))


def write_live_account_snapshot(
    snapshot: Mapping[str, Any],
    path: Path | str = LIVE_ACCOUNT_SNAPSHOT_PATH,
) -> Path:
    """Validate and atomically replace the sanitized account artifact."""
    payload = dict(snapshot)
    if not _valid_contract(payload):
        raise ValueError("INVALID_LIVE_ACCOUNT_SNAPSHOT_CONTRACT")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.{uuid4().hex}.tmp"
    )
    encoded = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def read_live_account_snapshot(
    path: Path | str = LIVE_ACCOUNT_SNAPSHOT_PATH,
    *,
    now: datetime | None = None,
    max_age_seconds: int = LIVE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS,
) -> dict[str, Any] | None:
    """Read a valid safe contract and derive staleness without broker access."""
    target = Path(path)
    try:
        if not target.is_file() or target.stat().st_size > 256_000:
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    read_at = _as_utc(now)
    if not _valid_contract(payload, now=read_at):
        return None
    generated_at = _parse_generated_at(payload["generated_at"])
    assert generated_at is not None
    result = dict(payload)
    if read_at - generated_at > timedelta(seconds=max(0, max_age_seconds)):
        result["status"] = "STALE"
        result["stale"] = True
        result["reason"] = "artifact_age_exceeded"
    return result


async def refresh_live_account_snapshot(
    path: Path | str = LIVE_ACCOUNT_SNAPSHOT_PATH,
    *,
    include_fills: bool = True,
    max_pages: int = LIVE_ACCOUNT_SNAPSHOT_MAX_PAGES,
    now: datetime | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run one bounded authenticated collection and atomically persist it."""
    generated_at = _as_utc(now)
    owns_client = client is None
    configuration_error = _credential_configuration_error() if client is None else None
    if configuration_error is not None:
        proof = {
            "get_only": True,
            "audit_valid": True,
            "total_requests": 0,
            "methods": [],
            "path_families": [],
            "endpoint_request_counts": {},
            "status_classes": [],
            "mutation_count": 0,
            "unexpected_path_count": 0,
            "blocked_attempt_count": 0,
        }
        invalid_endpoint = configuration_error == "INVALID_KALSHI_ENDPOINT"
        snapshot = _empty_snapshot(
            generated_at=generated_at,
            status="ERROR",
            stale=True,
            reason=(
                "invalid_endpoint_configuration"
                if invalid_endpoint
                else "missing_credentials"
            ),
            proof=proof,
            errors=[
                {
                    "stage": "credentials",
                    "code": configuration_error,
                    "retryable": False,
                }
            ],
        )
        write_live_account_snapshot(snapshot, path)
        return snapshot

    if client is None:
        from kalshi.client import KalshiClient

        client = KalshiClient()
    try:
        snapshot = await collect_live_account_snapshot(
            client=client,
            include_fills=include_fills,
            max_pages=max_pages,
            now=generated_at,
        )
        write_live_account_snapshot(snapshot, path)
        return snapshot
    finally:
        if owns_client:
            await client.close()
