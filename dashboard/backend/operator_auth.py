"""Operator-token guard for privileged dashboard routes.

Every state-changing or subprocess-triggering endpoint requires an explicitly
configured ``DUMMY_OPERATOR_TOKEN`` and a matching request header. Localhost is
not an authentication boundary: a browser can be induced to send requests to a
loopback service, so there is deliberately no same-machine bypass.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

ENV_VAR = "DUMMY_OPERATOR_TOKEN"


def _configured_token() -> str | None:
    return os.environ.get(ENV_VAR) or None


def _bears_valid_token(request: Request, token: str) -> bool:
    # Encode before compare_digest: a non-ASCII header value would otherwise
    # raise TypeError (500) instead of failing closed with 403.
    token_bytes = token.encode("utf-8")
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].encode("utf-8"), token_bytes):
        return True
    header = request.headers.get("x-operator-token", "")
    return bool(header) and hmac.compare_digest(header.encode("utf-8"), token_bytes)


def operator_auth_status(request: Request) -> dict[str, bool | str]:
    """Return setup/match booleans without ever returning the configured secret."""
    token = _configured_token()
    configured = token is not None
    return {
        "configured": configured,
        "authenticated": bool(configured and _bears_valid_token(request, token)),
        "secret_returned": False,
        "storage_policy": "browser_session_by_default",
    }


async def require_operator(request: Request) -> None:
    token = _configured_token()
    if token is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "operator token not configured; set DUMMY_OPERATOR_TOKEN before "
                "using state-changing or subprocess-backed routes"
            ),
        )
    if _bears_valid_token(request, token):
        return
    raise HTTPException(status_code=403, detail="missing or invalid operator token")
