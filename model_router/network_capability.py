"""Fail-closed authorization and endpoint policy for paid model networking.

The capability in this module is deliberately opaque.  Callers cannot create a
valid instance by constructing :class:`ModelNetworkCapability`; they must pass
the literal boolean ``True`` to :func:`issue_model_network_capability`.  Network
sinks then validate the private authority marker by identity.  This is not an
order/execution capability and grants no trading authority.
"""

from __future__ import annotations

from urllib.parse import urlsplit


class ModelNetworkAuthorizationError(RuntimeError):
    """Raised when a paid model-network sink lacks explicit authorization."""


class ProviderEndpointNotApproved(RuntimeError):
    """Raised before a credential is read when a provider endpoint is unsafe."""


_CAPABILITY_AUTHORITY = object()


class ModelNetworkCapability:
    """Opaque, process-local proof of a strict manual/config authorization."""

    __slots__ = ("_authority", "source")

    def __init__(self, *, _authority: object, source: str) -> None:
        if _authority is not _CAPABILITY_AUTHORITY:
            raise TypeError("ModelNetworkCapability cannot be constructed directly")
        self._authority = _authority
        self.source = source


def issue_model_network_capability(
    *,
    allow_live: bool,
    source: str,
) -> ModelNetworkCapability:
    """Mint an opaque capability only for the literal boolean ``True``.

    ``source`` is a non-secret audit label.  Truthy strings and integers are
    rejected so environment/config coercion cannot accidentally authorize a
    paid request.
    """

    if allow_live is not True:
        raise ModelNetworkAuthorizationError(
            "paid model network requires explicit allow_live=True"
        )
    if not isinstance(source, str) or not source.strip():
        raise ModelNetworkAuthorizationError(
            "paid model network capability requires a non-empty source"
        )
    return ModelNetworkCapability(
        _authority=_CAPABILITY_AUTHORITY,
        source=source.strip(),
    )


def model_network_capability_valid(capability: object) -> bool:
    """Return whether *capability* was minted by this module in this process."""

    return (
        isinstance(capability, ModelNetworkCapability)
        and capability._authority is _CAPABILITY_AUTHORITY
    )


def require_model_network_capability(capability: object) -> None:
    """Fail closed unless *capability* is an authentic process-local token."""

    if not model_network_capability_valid(capability):
        raise ModelNetworkAuthorizationError(
            "paid model network capability is missing or invalid"
        )


APPROVED_MODEL_PROVIDER_HTTPS_HOSTS = frozenset(
    {
        "openrouter.ai",
        "api.deepseek.com",
        "api.minimax.chat",
    }
)

_APPROVED_HOSTS_BY_CREDENTIAL = {
    "OPENROUTER_API_KEY": frozenset({"openrouter.ai"}),
    "DEEPSEEK_API_KEY": frozenset({"api.deepseek.com"}),
    "MINIMAX_API_KEY": frozenset({"api.minimax.chat"}),
}


def validate_model_provider_endpoint(api_base: str, api_key_env: str) -> str:
    """Validate HTTPS host and credential-to-host binding before key access.

    Returns the normalized hostname.  User-info, non-default ports, fragments,
    unknown hosts, and a credential intended for another provider are rejected.
    """

    try:
        parsed = urlsplit(api_base)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ProviderEndpointNotApproved("provider API base is malformed") from exc

    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
    ):
        raise ProviderEndpointNotApproved(
            "provider endpoint must be credential-free HTTPS on port 443"
        )
    if host not in APPROVED_MODEL_PROVIDER_HTTPS_HOSTS:
        raise ProviderEndpointNotApproved("provider endpoint host is not approved")

    approved_for_key = _APPROVED_HOSTS_BY_CREDENTIAL.get(api_key_env)
    if approved_for_key is None or host not in approved_for_key:
        raise ProviderEndpointNotApproved(
            "provider credential is not approved for the endpoint host"
        )
    return host
