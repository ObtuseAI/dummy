"""Provider route-mode resolution: OpenRouter vs provider-native.

``ProviderRouteModeResolver`` inspects the configured base URL and model name
for a provider and decides whether the operator intends to call the provider
natively or through OpenRouter.  The route mode then determines which API key
should be checked and which endpoint conventions apply.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProviderRouteMode(str, Enum):
    """Supported provider routing modes."""

    PROVIDER_NATIVE_DEEPSEEK = "provider_native_deepseek"
    PROVIDER_NATIVE_MINIMAX = "provider_native_minimax"
    OPENROUTER = "openrouter"
    MOCK_ONLY = "mock_only"
    OPERATOR_CONFIG_REQUIRED = "operator_config_required"


@dataclass(frozen=True)
class ProviderRouteModeResult:
    """Redacted route-mode resolution result."""

    provider_name: str
    route_mode: ProviderRouteMode
    intended_key_env: str
    key_present: bool
    base_url_class: str  # e.g. "openrouter", "deepseek_native", "unknown"
    configured_model: str
    reason: str
    redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "route_mode": self.route_mode.value,
            "intended_key_env": self.intended_key_env,
            "key_present": self.key_present,
            "base_url_class": self.base_url_class,
            "configured_model": self.configured_model,
            "reason": self.reason,
            "redacted": True,
        }


class ProviderRouteModeResolver:
    """Resolve route mode and intended credential key for a provider."""

    # URL fragments that unambiguously identify a route.
    _OPENROUTER_HOSTS = ("openrouter.ai", "openrouter.com")
    _DEEPSEEKK_HOSTS = ("api.deepseek.com", "deepseek.com")
    _MINIMAX_HOSTS = ("api.minimax.chat", "minimax.chat", "minimax.com")

    def __init__(self, credential_resolver=None):
        # Lazy import avoids circular dependency.
        if credential_resolver is None:
            from model_router.credential_source import ProviderCredentialSourceResolver

            self._credential_resolver = ProviderCredentialSourceResolver()
        else:
            self._credential_resolver = credential_resolver

    def _base_url_class(self, base_url: str) -> str:
        lowered = base_url.lower()
        if any(host in lowered for host in self._OPENROUTER_HOSTS):
            return "openrouter"
        if any(host in lowered for host in self._DEEPSEEKK_HOSTS):
            return "deepseek_native"
        if any(host in lowered for host in self._MINIMAX_HOSTS):
            return "minimax_native"
        return "unknown"

    def _looks_like_openrouter_model(self, model: str) -> bool:
        # OpenRouter model IDs are typically "provider/model-name".
        return "/" in model and not model.endswith("/")

    def resolve(
        self,
        provider_name: str,
        base_url: str,
        configured_model: str,
        route_mode_override: str | None = None,
    ) -> ProviderRouteModeResult:
        """Return route mode and intended key env for *provider_name*.

        *provider_name* is the internal slug (e.g. ``deepseek_v4_flash``).
        *base_url* is the resolved API base.
        *configured_model* is the model slug currently in config/env.
        *route_mode_override* optionally forces a mode.
        """
        if route_mode_override:
            try:
                mode = ProviderRouteMode(route_mode_override)
            except ValueError:
                mode = ProviderRouteMode.OPERATOR_CONFIG_REQUIRED
        else:
            url_class = self._base_url_class(base_url)
            is_openrouter_model = self._looks_like_openrouter_model(configured_model)

            if url_class == "openrouter" or is_openrouter_model:
                mode = ProviderRouteMode.OPENROUTER
            elif url_class == "deepseek_native" or "deepseek" in provider_name.lower():
                mode = ProviderRouteMode.PROVIDER_NATIVE_DEEPSEEK
            elif url_class == "minimax_native" or "minimax" in provider_name.lower():
                mode = ProviderRouteMode.PROVIDER_NATIVE_MINIMAX
            else:
                mode = ProviderRouteMode.OPERATOR_CONFIG_REQUIRED

        intended_key_env, reason = self._key_env_and_reason(
            provider_name, mode, base_url, configured_model
        )

        key_present = self._credential_resolver.resolve(intended_key_env).present

        return ProviderRouteModeResult(
            provider_name=provider_name,
            route_mode=mode,
            intended_key_env=intended_key_env,
            key_present=key_present,
            base_url_class=self._base_url_class(base_url),
            configured_model=configured_model,
            reason=reason,
        )

    def _key_env_and_reason(
        self,
        provider_name: str,
        mode: ProviderRouteMode,
        base_url: str,
        configured_model: str,
    ) -> tuple[str, str]:
        if mode == ProviderRouteMode.OPENROUTER:
            return (
                "OPENROUTER_API_KEY",
                f"base_url/model '{configured_model}' indicate OpenRouter route",
            )
        if mode == ProviderRouteMode.PROVIDER_NATIVE_DEEPSEEK:
            return (
                "DEEPSEEK_API_KEY",
                "native DeepSeek endpoint selected",
            )
        if mode == ProviderRouteMode.PROVIDER_NATIVE_MINIMAX:
            return (
                "MINIMAX_API_KEY",
                "native Minimax endpoint selected",
            )
        if mode == ProviderRouteMode.MOCK_ONLY:
            return ("", "mock-only mode configured")
        # operator_config_required
        if "deepseek" in provider_name.lower():
            return (
                "DEEPSEEK_API_KEY",
                f"unrecognized base_url '{base_url}' and model '{configured_model}'",
            )
        if "minimax" in provider_name.lower():
            return (
                "MINIMAX_API_KEY",
                f"unrecognized base_url '{base_url}' and model '{configured_model}'",
            )
        return ("", f"unrecognized provider '{provider_name}'")
