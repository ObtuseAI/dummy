from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx


PENDING_RETRY = "PENDING_RETRY"
PENDING_REVIEW = "PENDING_REVIEW"
MAX_HARVEST_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.1
MAX_RETRY_DELAY_SECONDS = 1.0

_TRANSIENT_HTTP_STATUS_CODES = {
    408,
    409,
    425,
    429,
    500,
    502,
    503,
    504,
}

T = TypeVar("T")


class HarvestRetryExhausted(RuntimeError):
    """A transient harvester operation failed for every bounded attempt."""

    def __init__(self, cause: BaseException, attempts: int) -> None:
        self.cause = cause
        self.attempts = attempts
        super().__init__(
            f"transient harvest failure after {attempts} attempts: "
            f"{type(cause).__name__}: {cause}"
        )


def is_transient_harvest_error(exc: BaseException) -> bool:
    """Return whether retrying *exc* can plausibly succeed without a code change."""

    if isinstance(exc, HarvestRetryExhausted):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_HTTP_STATUS_CODES
    return False


async def run_with_bounded_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = MAX_HARVEST_ATTEMPTS,
    base_delay_seconds: float = BASE_RETRY_DELAY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run an async harvest operation with a small, bounded transient retry budget.

    Permanent errors are surfaced immediately. Transient errors are never converted
    into permanent repository verdicts here; exhaustion is represented by the
    dedicated ``HarvestRetryExhausted`` exception for the caller to quarantine.
    """

    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            if not is_transient_harvest_error(exc):
                raise
            if attempt >= attempts:
                raise HarvestRetryExhausted(exc, attempts) from exc
            delay = min(
                MAX_RETRY_DELAY_SECONDS,
                max(0.0, base_delay_seconds) * (2 ** (attempt - 1)),
            )
            await sleep(delay)

    raise AssertionError("bounded retry loop terminated without a result")
