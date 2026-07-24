from __future__ import annotations
import time
from typing import Any
from model_router.config import ModelRoutingConfig, load_model_routing_config
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider, OpenRouterProvider
from model_router.cli_providers import ClaudeCliProvider, CodexCliProvider
from model_router.prompt_firewall import PromptFirewall
from model_router.tasks import ModelTask
from model_router.cost_tracker import CostTracker
from model_router.network_capability import issue_model_network_capability
from model_router.spend_governor import (
    REASON_CAP_REACHED,
    LlmSpendGovernor,
    SpendDecision,
    estimate_call_cost_usd,
    is_metered_route,
)

_PROVIDER_CLASSES = {
    "deepseek_v4_flash": DeepSeekV4FlashProvider,
    "minimax_m3": MinimaxM3Provider,
    # Wave-34: local-CLI panelists (own auth, no OpenRouter key). Gated OFF by
    # default (DUMMY_CLI_PROVIDERS=1) since they bill personal subscriptions.
    "claude_cli": ClaudeCliProvider,
    "codex_cli": CodexCliProvider,
    "mock": MockProvider,
}


def _reported_cost_usd(metadata: dict | None) -> float | None:
    """The provider's own reported cost, or None when it reported nothing."""
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("cost_usd")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class ModelRouter:
    def __init__(
        self,
        config_path: Any | None = None,
        *,
        spend_governor: LlmSpendGovernor | None = None,
    ):
        self.config: ModelRoutingConfig = load_model_routing_config(config_path)
        self.providers: dict[str, Any] = {}
        self._init_providers()
        self.prompt_firewall = PromptFirewall(
            self.config.blocked_prompt_categories,
            self.config.secret_key_env_names,
        )
        self.cost_tracker = CostTracker()
        # Observation (cost_tracker) is per-process and dies with the cycle;
        # ENFORCEMENT (spend_governor) is a persisted daily USD ceiling that
        # survives the process-per-cycle brain.
        self.spend_governor = spend_governor or LlmSpendGovernor()

    def _init_providers(self):
        for name, pc in self.config.provider_configs.items():
            cls = _PROVIDER_CLASSES.get(name)
            if cls is None:
                # Unknown provider name: use the generic OpenRouter adapter when
                # it's an OpenRouter route, otherwise fall back to mock. This
                # lets the config add arbitrary panel models without code edits.
                cls = OpenRouterProvider if getattr(pc, "route_mode", None) == "openrouter" else MockProvider
            self.providers[name] = cls(pc)
        self.providers.setdefault("mock", MockProvider())

    def route(self, task: ModelTask) -> ModelRouteDecision:
        default = self.config.default_provider.get(task.value, "mock")
        if default == "hybrid":
            # Hybrid callers request both configured voices. A direct HYBRID_REVIEW
            # call routes to the first voice; the panel caller adds the skeptic.
            default = next(iter(self.config.hybrid_providers), "mock")
        pc = self.config.provider_configs.get(default)
        model = pc.model_name if pc else "mock"
        if not self.providers[default].available:
            return ModelRouteDecision(
                task=task,
                provider_name="mock",
                model_name="mock",
                reason="preferred provider unavailable",
                fallback_reason=f"{default}_credentials_missing",
            )
        return ModelRouteDecision(
            task=task,
            provider_name=default,
            model_name=model,
            reason="task default provider",
        )

    def available_real_providers(self) -> list[str]:
        """Names of configured non-mock providers with usable credentials."""
        return [name for name, p in self.providers.items()
                if name != "mock" and getattr(p, "available", False)]

    def hybrid_provider_names(self) -> list[str]:
        """Configured hybrid voices that are real and currently available."""
        return [
            name for name in self.config.hybrid_providers
            if name in self.providers and getattr(self.providers[name], "available", False)
        ]

    async def call(self, task: ModelTask, prompt: str, context: dict | None = None, max_tokens: int = 512, temperature: float = 0.2, provider_override: str | None = None) -> ModelResponseEnvelope:
        blocked = self.prompt_firewall.block_check(prompt)
        sanitized = self.prompt_firewall.sanitize(prompt)
        if blocked:
            return ModelResponseEnvelope(
                task=task,
                decision=ModelRouteDecision(task=task, provider_name="none", model_name="none", reason="blocked"),
                prompt=sanitized,
                content="",
                raw_metadata={"context": context or {}},
                latency_ms=0.0,
                blocked_by=blocked,
            )
        if provider_override and provider_override in self.providers and self.providers[provider_override].available:
            pc = self.config.provider_configs.get(provider_override)
            decision = ModelRouteDecision(
                task=task, provider_name=provider_override,
                model_name=pc.model_name if pc else provider_override,
                reason="panel provider override",
            )
        else:
            decision = self.route(task)
        provider = self.providers[decision.provider_name]
        provider_config = self.config.provider_configs.get(decision.provider_name)
        # ENFORCED daily USD ceiling.  Only a call that can actually leave the
        # process spends money, so the budget is charged after the live-config
        # gate and never for mock or subscription-billed CLI voices.
        reservation: SpendDecision | None = None
        if self.config.live_model_calls_enabled is True and is_metered_route(
            decision.provider_name, provider_config
        ):
            reservation = self.spend_governor.reserve(
                estimate_call_cost_usd(provider_config, sanitized, max_tokens)
            )
            if not reservation.allowed:
                return await self._spend_capped_envelope(
                    task, sanitized, context, reservation, max_tokens, temperature
                )
        started = time.monotonic()
        billed_metadata: dict | None = None
        try:
            if self.config.live_model_calls_enabled is not True:
                raise RuntimeError("live_model_calls_enabled is false")
            # Mint the opaque provider-network capability only after the strict
            # checked config gate.  The provider sink independently verifies it.
            network_capability = issue_model_network_capability(
                allow_live=True,
                source="model_router.checked_live_config",
            )
            content_text, metadata = await provider.complete(
                sanitized,
                task,
                max_tokens,
                temperature,
                network_capability=network_capability,
            )
            billed_metadata = metadata if isinstance(metadata, dict) else None
        except Exception:
            if not self.config.mock_fallback_enabled:
                # The reservation is deliberately NOT released: a request that
                # left the process may have been billed even though it failed.
                raise
            fallback_reason = f"{decision.provider_name}_request_failed" if self.config.live_model_calls_enabled else "live_calls_disabled"
            decision = ModelRouteDecision(
                task=task,
                provider_name="mock",
                model_name="mock",
                reason="provider fallback",
                fallback_reason=fallback_reason,
            )
            provider = self.providers["mock"]
            content_text, metadata = await provider.complete(sanitized, task, max_tokens, temperature)
        latency_ms = (time.monotonic() - started) * 1000
        if reservation is not None:
            # Reconcile the reservation against what the provider says it
            # charged (measured after latency so ledger I/O is not billed to
            # the model's response time).
            self.spend_governor.settle(
                reservation, _reported_cost_usd(billed_metadata))
        safe_content = self.prompt_firewall.redact_response(content_text)
        envelope = ModelResponseEnvelope(
            task=task,
            decision=decision,
            prompt=sanitized,
            content=safe_content,
            raw_metadata={**metadata, "context": context or {}},
            latency_ms=latency_ms,
        )
        self.cost_tracker.record(envelope)
        return envelope

    async def _spend_capped_envelope(
        self,
        task: ModelTask,
        sanitized: str,
        context: dict | None,
        reservation: SpendDecision,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponseEnvelope:
        """Refuse a paid call that would cross the enforced daily USD cap.

        The paid provider is never contacted.  The reason rides on
        ``fallback_reason`` exactly like the closed live gate -- and on
        ``blocked_by`` when there is no mock voice to degrade to -- so every
        existing caller (debate panel, analyst signal, real-market review)
        discards it instead of mistaking a free voice for the model it asked
        for.
        """
        reason = reservation.reason or REASON_CAP_REACHED
        spend_metadata = {
            "spend_cap": reservation.as_dict(),
            "context": context or {},
        }
        decision = ModelRouteDecision(
            task=task,
            provider_name="mock" if self.config.mock_fallback_enabled else "none",
            model_name="mock" if self.config.mock_fallback_enabled else "none",
            reason="daily spend cap",
            fallback_reason=reason,
        )
        if not self.config.mock_fallback_enabled:
            return ModelResponseEnvelope(
                task=task,
                decision=decision,
                prompt=sanitized,
                content="",
                raw_metadata=spend_metadata,
                latency_ms=0.0,
                blocked_by=reason,
            )
        started = time.monotonic()
        content_text, metadata = await self.providers["mock"].complete(
            sanitized, task, max_tokens, temperature)
        envelope = ModelResponseEnvelope(
            task=task,
            decision=decision,
            prompt=sanitized,
            content=self.prompt_firewall.redact_response(content_text),
            raw_metadata={**metadata, **spend_metadata},
            latency_ms=(time.monotonic() - started) * 1000,
        )
        self.cost_tracker.record(envelope)
        return envelope

    def spend_status(self) -> dict[str, Any]:
        """Today's enforced budget, safe to log alongside the cost summary."""
        return self.spend_governor.status()
