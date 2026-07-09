"""Provider-agnostic error classification for live model adapters.

Exports a single function, ``classify_provider_error``, that maps an exception
to a stable string tag such as ``TIMEOUT`` or ``HTTP_429``.  These tags are
safe to log and safe to store in metadata because they never contain API keys,
raw prompts, or raw response bodies.
"""
from __future__ import annotations

import httpx


class ProviderResponseSchemaError(ValueError):
    """Raised when a provider response does not match the expected task schema."""

    def __init__(self, message: str):
        super().__init__(message)
        self.error_class = "SCHEMA_VALIDATION"


def classify_provider_error(exc: Exception) -> str:
    """Return a stable, redacted error-class tag for *exc*.

    Tags are intentionally coarse-grained so they can be used in metrics and
    reports without leaking sensitive request/response content.
    """
    if isinstance(exc, ProviderResponseSchemaError):
        return exc.error_class

    if isinstance(exc, httpx.TimeoutException):
        return "TIMEOUT"

    if isinstance(exc, httpx.ConnectError):
        return "CONNECT_ERROR"

    if isinstance(exc, httpx.NetworkError):
        return "NETWORK_ERROR"

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "HTTP_429"
        if status >= 500:
            return f"HTTP_{status}"
        if status >= 400:
            return f"HTTP_{status}"
        return "HTTP_ERROR"

    return "PROVIDER_ERROR"


def classify_provider_error_v2(exc: Exception, path: str = "") -> str:
    """Return a provider-facing error category for *exc*.

    The returned category is safe to log and store (no prompt/response/key
    content).  HTTP 404 is disambiguated based on the request path.
    """
    base = classify_provider_error(exc)

    if base == "HTTP_404":
        if "/models" in path:
            return "ENDPOINT_NOT_FOUND"
        if "/chat/completions" in path:
            return "MODEL_NOT_FOUND"
        return "PROVIDER_ROUTE_NOT_FOUND"

    if base == "HTTP_401" or base == "HTTP_403":
        return "PROVIDER_AUTH_FAILED"

    if base == "HTTP_429":
        return "PROVIDER_RATE_LIMITED"

    if base == "TIMEOUT":
        return "PROVIDER_TIMEOUT"

    if base in ("CONNECT_ERROR", "NETWORK_ERROR"):
        return "PROVIDER_NETWORK_ERROR"

    if base == "SCHEMA_VALIDATION":
        return "PROVIDER_SCHEMA_ERROR"

    return base
