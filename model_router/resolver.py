"""Bounded, redacted live-model provider resolution.

``ModelProviderResolver`` determines whether configured DeepSeekV4Flash and
MinimaxM3 credentials/model IDs can actually be exercised.  It tries an
OpenAI-compatible model-list endpoint first, then falls back to bounded
alias-smoke calls.  No API key values, raw prompts, or raw responses are
stored or returned.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from model_router.config import ProviderConfig, load_model_routing_config
from model_router.credential_source import ProviderCredentialSourceResolver
from model_router.error_classifier import classify_provider_error_v2
from model_router.network_capability import (
    ModelNetworkCapability,
    ProviderEndpointNotApproved,
    model_network_capability_valid,
    require_model_network_capability,
    validate_model_provider_endpoint,
)
from model_router.prompt_firewall import PromptFirewallV2
from model_router.route_mode import ProviderRouteModeResolver


_DEFAULT_BASE_URLS: dict[str, str] = {
    "deepseek_v4_flash": "https://api.deepseek.com",
    "minimax_m3": "https://api.minimax.chat",
}

_DEFAULT_ALIASES: dict[str, list[str]] = {
    "deepseek_v4_flash": [
        "deepseek-chat",
        "deepseek-v3",
        "deepseek/deepseek-v3",
        "deepseek-v4-flash",
    ],
    "minimax_m3": [
        "minimax-01",
        "MiniMax-Text-01",
        "minimax/minimax-01",
    ],
}

# A failed model-list lookup may fall back to paid chat probes, but never to an
# operator-controlled, unbounded alias fan-out.
MAX_ALIAS_PROBES = 8


def _provider_env_prefix(provider_name: str) -> str:
    if "deepseek" in provider_name.lower():
        return "DEEPSEEK"
    if "minimax" in provider_name.lower():
        return "MINIMAX"
    return provider_name.upper()


@dataclass
class ProviderEndpointCandidate:
    """A base URL + credential env for a provider."""

    provider_name: str
    api_base: str
    api_key_env: str
    timeout_seconds: float = 10.0


@dataclass
class ModelAliasCandidate:
    """A model slug to try resolving."""

    model_name: str
    source: str  # "config", "env", "default"


@dataclass
class ProviderResolutionResult:
    """Redacted result of attempting to resolve a live provider."""

    provider_name: str
    status: str  # LIVE_PROVEN, OPERATOR_MODEL_CONFIG_REQUIRED, PROVIDER_AUTH_FAILED, MOCK_ONLY
    api_base: str
    api_key_env: str
    configured_model: str
    resolved_model: str | None = None
    resolved_by: str | None = None  # "model_list", "alias_smoke"
    error_category: str | None = None
    error_detail: str | None = None
    credential_source: str | None = None
    route_mode: str | None = None
    redacted_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        credential_resolver = ProviderCredentialSourceResolver()
        route_resolver = ProviderRouteModeResolver(credential_resolver)
        route_result = route_resolver.resolve(
            self.provider_name, self.api_base, self.configured_model
        )
        credential_resolution = credential_resolver.resolve(self.api_key_env)
        self.redacted_metadata = {
            "provider_name": self.provider_name,
            "status": self.status,
            "api_base_present": bool(self.api_base),
            "api_key_env": self.api_key_env,
            "api_key_present": credential_resolution.present,
            "credential_source": credential_resolution.source.value,
            "configured_model": self.configured_model,
            "resolved_model": self.resolved_model,
            "resolved_by": self.resolved_by,
            "error_category": self.error_category,
            "error_detail": self.error_detail,
            "route_mode": route_result.route_mode.value,
            "intended_key_env": route_result.intended_key_env,
            "base_url_class": route_result.base_url_class,
        }


class ModelProviderResolver:
    """Resolve a provider/model endpoint without leaking secrets."""

    def __init__(self):
        self._cfg = load_model_routing_config()
        self._firewall = PromptFirewallV2()
        self._credential_resolver = ProviderCredentialSourceResolver()
        self._route_resolver = ProviderRouteModeResolver(self._credential_resolver)

    def _provider_config(self, name: str) -> ProviderConfig:
        return self._cfg.provider_configs.get(
            name,
            ProviderConfig(api_base="", api_key_env="", model_name=""),
        )

    def _endpoint_candidate(
        self, name: str, default_base: str
    ) -> ProviderEndpointCandidate:
        cfg = self._provider_config(name)
        prefix = _provider_env_prefix(name)
        api_base = (
            os.environ.get(f"{prefix}_BASE_URL")
            or cfg.api_base
            or default_base
        )
        configured_model = self._configured_model(name)
        prefix = _provider_env_prefix(name)
        route_override = (
            os.environ.get(f"{prefix}_ROUTE_MODE")
            or getattr(cfg, "route_mode", None)
        )
        route_result = self._route_resolver.resolve(
            name, api_base, configured_model, route_mode_override=route_override
        )
        # The route resolver tells us which key is intended for this endpoint.
        # Fall back to the provider-specific env name if the resolver cannot decide.
        api_key_env = route_result.intended_key_env or cfg.api_key_env or f"{prefix}_API_KEY"
        timeout = min(getattr(cfg, "timeout_seconds", 20.0), 20.0)
        return ProviderEndpointCandidate(
            provider_name=name,
            api_base=api_base,
            api_key_env=api_key_env,
            timeout_seconds=timeout,
        )

    def _configured_model(self, name: str) -> str:
        cfg = self._provider_config(name)
        prefix = _provider_env_prefix(name)
        return os.environ.get(f"{prefix}_MODEL") or cfg.model_name or ""

    def _aliases(self, name: str, default_aliases: list[str]) -> list[ModelAliasCandidate]:
        cfg = self._provider_config(name)
        prefix = _provider_env_prefix(name)

        aliases: list[ModelAliasCandidate] = []
        seen: set[str] = set()

        # Config aliases
        for alias in getattr(cfg, "model_aliases", []) or []:
            if alias and alias not in seen:
                aliases.append(ModelAliasCandidate(alias, "config"))
                seen.add(alias)

        # Env aliases
        raw = os.environ.get(f"{prefix}_MODEL_ALIASES", "")
        for alias in raw.split(","):
            alias = alias.strip()
            if alias and alias not in seen:
                aliases.append(ModelAliasCandidate(alias, "env"))
                seen.add(alias)

        # Default aliases
        for alias in default_aliases:
            if alias and alias not in seen:
                aliases.append(ModelAliasCandidate(alias, "default"))
                seen.add(alias)

        # Ensure configured model is tried first if set
        configured = self._configured_model(name)
        if configured and configured not in seen:
            aliases.insert(0, ModelAliasCandidate(configured, "config"))

        return aliases

    async def _probe_model_list(
        self,
        candidate: ProviderEndpointCandidate,
        *,
        network_capability: ModelNetworkCapability,
    ) -> tuple[bool, list[str]]:
        require_model_network_capability(network_capability)
        validate_model_provider_endpoint(candidate.api_base, candidate.api_key_env)
        key = self._credential_resolver.get_value(candidate.api_key_env)
        if not key:
            return False, []
        url = f"{candidate.api_base.rstrip('/')}/v1/models"
        try:
            async with httpx.AsyncClient(
                timeout=min(candidate.timeout_seconds, 10.0)
            ) as client:
                r = await client.get(
                    url, headers={"Authorization": f"Bearer {key}"}
                )
                r.raise_for_status()
                data = r.json()
                models = [
                    str(m.get("id", ""))
                    for m in data.get("data", [])
                    if isinstance(m, dict)
                ]
                return True, models
        except Exception:
            return False, []

    async def _probe_alias(
        self,
        candidate: ProviderEndpointCandidate,
        alias: ModelAliasCandidate,
        prompt: str,
        *,
        network_capability: ModelNetworkCapability,
    ) -> tuple[bool, str | None]:
        require_model_network_capability(network_capability)
        validate_model_provider_endpoint(candidate.api_base, candidate.api_key_env)
        key = self._credential_resolver.get_value(candidate.api_key_env)
        if not key:
            return False, "PROVIDER_AUTH_FAILED"

        sanitized = self._firewall.sanitize(prompt)
        decision = self._firewall.block_check(sanitized)
        if not decision.allowed:
            return False, "PROMPT_FIREWALL_BLOCK"

        url = f"{candidate.api_base.rstrip('/')}/v1/chat/completions"
        body: dict[str, Any] = {
            "model": alias.model_name,
            "messages": [{"role": "user", "content": sanitized}],
            "max_tokens": 16,
        }
        try:
            async with httpx.AsyncClient(
                timeout=min(candidate.timeout_seconds, 10.0)
            ) as client:
                r = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                return True, None
        except Exception as exc:
            return False, classify_provider_error_v2(exc, path="/v1/chat/completions")

    async def resolve(
        self,
        name: str,
        default_base: str | None = None,
        default_aliases: list[str] | None = None,
        smoke_prompt: str | None = None,
        *,
        allow_live: bool = False,
        network_capability: ModelNetworkCapability | None = None,
    ) -> ProviderResolutionResult:
        """Resolve provider endpoint and model.

        Credential/config inspection is local.  Provider contact occurs only
        when ``allow_live is True`` and a valid process-local network
        capability is supplied.
        """
        default_base = default_base or _DEFAULT_BASE_URLS.get(name, "")
        default_aliases = default_aliases or _DEFAULT_ALIASES.get(name, [])
        candidate = self._endpoint_candidate(name, default_base)
        configured = self._configured_model(name)
        aliases = self._aliases(name, default_aliases)

        try:
            validate_model_provider_endpoint(
                candidate.api_base,
                candidate.api_key_env,
            )
        except ProviderEndpointNotApproved:
            return ProviderResolutionResult(
                provider_name=name,
                status="OPERATOR_MODEL_CONFIG_REQUIRED",
                api_base=candidate.api_base,
                api_key_env=candidate.api_key_env,
                configured_model=configured,
                error_category="PROVIDER_ENDPOINT_NOT_APPROVED",
                error_detail=(
                    "provider endpoint or credential-to-host binding is not approved"
                ),
            )

        credential_resolution = self._credential_resolver.resolve(candidate.api_key_env)
        if not credential_resolution.present:
            route_result = self._route_resolver.resolve(
                name, candidate.api_base, configured
            )
            return ProviderResolutionResult(
                provider_name=name,
                status="MOCK_ONLY",
                api_base=candidate.api_base,
                api_key_env=candidate.api_key_env,
                configured_model=configured,
                credential_source=credential_resolution.source.value,
                route_mode=route_result.route_mode.value,
            )

        if allow_live is not True or not model_network_capability_valid(
            network_capability
        ):
            route_result = self._route_resolver.resolve(
                name, candidate.api_base, configured
            )
            return ProviderResolutionResult(
                provider_name=name,
                status="PREFLIGHT_ONLY",
                api_base=candidate.api_base,
                api_key_env=candidate.api_key_env,
                configured_model=configured,
                credential_source=credential_resolution.source.value,
                route_mode=route_result.route_mode.value,
                error_category="LIVE_AUTHORIZATION_REQUIRED",
                error_detail="provider contact requires explicit strict live authorization",
            )

        # 1. Try model list
        list_ok, models = await self._probe_model_list(
            candidate,
            network_capability=network_capability,
        )
        if list_ok:
            if configured and configured in models:
                return ProviderResolutionResult(
                    provider_name=name,
                    status="LIVE_PROVEN",
                    api_base=candidate.api_base,
                    api_key_env=candidate.api_key_env,
                    configured_model=configured,
                    resolved_model=configured,
                    resolved_by="model_list",
                )
            # Try aliases against the published list
            for alias in aliases:
                if alias.model_name in models:
                    return ProviderResolutionResult(
                        provider_name=name,
                        status="LIVE_PROVEN",
                        api_base=candidate.api_base,
                        api_key_env=candidate.api_key_env,
                        configured_model=configured,
                        resolved_model=alias.model_name,
                        resolved_by="model_list",
                    )

        # 2. Try alias smoke calls
        prompt = smoke_prompt or _harmless_prompt_for(name)
        last_error: str | None = None
        auth_failed = False
        for alias in aliases[:MAX_ALIAS_PROBES]:
            ok, err = await self._probe_alias(
                candidate,
                alias,
                prompt,
                network_capability=network_capability,
            )
            if ok:
                return ProviderResolutionResult(
                    provider_name=name,
                    status="LIVE_PROVEN",
                    api_base=candidate.api_base,
                    api_key_env=candidate.api_key_env,
                    configured_model=configured,
                    resolved_model=alias.model_name,
                    resolved_by="alias_smoke",
                )
            if err == "PROVIDER_AUTH_FAILED":
                auth_failed = True
            last_error = err

        status = "PROVIDER_AUTH_FAILED" if auth_failed else "OPERATOR_MODEL_CONFIG_REQUIRED"
        return ProviderResolutionResult(
            provider_name=name,
            status=status,
            api_base=candidate.api_base,
            api_key_env=candidate.api_key_env,
            configured_model=configured,
            error_category=last_error or "UNKNOWN",
            error_detail=(
                "configured model and all aliases were unresolved"
                if not auth_failed
                else "credentials were rejected by the provider"
            ),
        )

    def audit_provider_config(
        self, name: str, default_base: str, default_aliases: list[str]
    ) -> dict[str, Any]:
        """Return a redacted audit of the provider's configuration."""
        candidate = self._endpoint_candidate(name, default_base)
        configured = self._configured_model(name)
        aliases = self._aliases(name, default_aliases)
        credential_resolution = self._credential_resolver.resolve(candidate.api_key_env)
        route_result = self._route_resolver.resolve(name, candidate.api_base, configured)
        return {
            "provider_name": name,
            "api_key_env": candidate.api_key_env,
            "api_key_present": credential_resolution.present,
            "credential_source": credential_resolution.source.value,
            "api_base": candidate.api_base,
            "base_url_class": route_result.base_url_class,
            "configured_model": configured,
            "route_mode": route_result.route_mode.value,
            "intended_key_env": route_result.intended_key_env,
            "alias_count": len(aliases),
            "alias_sources": sorted({a.source for a in aliases}),
            "timeout_seconds": candidate.timeout_seconds,
        }


def _harmless_prompt_for(provider_name: str) -> str:
    if "deepseek" in provider_name.lower():
        return (
            "Provide a concise neutral market summary in one sentence. "
            "Return only a JSON object with keys 'thesis' and 'confidence'."
        )
    return (
        "Provide a concise risk critique of broad market conditions in one sentence. "
        "Return only a JSON object with keys 'risk_level' and 'reasoning'."
    )
