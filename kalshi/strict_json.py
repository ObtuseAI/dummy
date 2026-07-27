"""Bounded strict JSON decoding for untrusted Kalshi HTTP responses."""

from __future__ import annotations

import json
import math
from typing import Any, Protocol

MAX_KALSHI_JSON_RESPONSE_BYTES = 8 * 1024 * 1024


class StrictJSONResponseError(ValueError):
    """Raised when a broker response is not bounded strict UTF-8 JSON."""


class _ByteResponse(Protocol):
    @property
    def content(self) -> bytes: ...


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictJSONResponseError(
                "Kalshi response contains duplicate JSON keys"
            )
        value[key] = item
    return value


def _reject_non_finite(token: str) -> None:
    raise StrictJSONResponseError(
        f"Kalshi response contains non-finite JSON value {token}"
    )


def _parse_finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        _reject_non_finite(token)
    return value


def load_strict_json_response(
    response: _ByteResponse,
    *,
    maximum_bytes: int = MAX_KALSHI_JSON_RESPONSE_BYTES,
) -> Any:
    """Decode one fully buffered response without permissive JSON extensions."""
    if not isinstance(maximum_bytes, int) or isinstance(maximum_bytes, bool):
        raise TypeError("maximum_bytes must be an integer")
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")

    body = response.content
    if not isinstance(body, bytes):
        raise StrictJSONResponseError("Kalshi response body must be bytes")
    if len(body) > maximum_bytes:
        raise StrictJSONResponseError(
            f"Kalshi response exceeds {maximum_bytes} byte limit"
        )

    try:
        text = body.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
            parse_float=_parse_finite_float,
        )
    except StrictJSONResponseError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StrictJSONResponseError(
            "Kalshi response is not valid strict UTF-8 JSON"
        ) from exc
