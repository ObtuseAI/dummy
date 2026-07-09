"""Transport guard that allows only read-only HTTP methods.

This is intended to wrap an httpx-style client so that any accidental
POST/PATCH/PUT/DELETE request to a live broker is blocked before it leaves
the process.
"""
from __future__ import annotations

from typing import Any


class ReadOnlyTransportGuard:
    """Async client wrapper that permits GET/HEAD and blocks writes.

    Usable as a drop-in replacement for ``httpx.AsyncClient`` on
    ``kalshi.client.KalshiClient.client``.  Blocked attempts are recorded in
    ``blocked_attempts`` for test/audit verification.
    """

    ALLOWED_METHODS = {"GET", "HEAD"}

    def __init__(self, client: Any | None = None, test_mode: bool = False):
        self.client = client
        self.test_mode = test_mode
        self.blocked_attempts: list[dict[str, Any]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not isinstance(method, str):
            raise ValueError(f"HTTP method must be a string, got {type(method).__name__}")

        normalized = method.upper()
        if normalized not in self.ALLOWED_METHODS:
            entry = {"method": normalized, "path": path}
            self.blocked_attempts.append(entry)
            raise RuntimeError(
                f"ReadOnlyTransportGuard blocked {normalized} {path}: only GET/HEAD allowed."
            )

        if self.client is None:
            raise RuntimeError(
                "ReadOnlyTransportGuard has no underlying client to execute GET/HEAD."
            )

        return await self.client.request(method, path, **kwargs)

    async def aclose(self) -> None:
        """Delegate close to the underlying client if it supports it."""
        if self.client is not None and hasattr(self.client, "aclose"):
            await self.client.aclose()
