from __future__ import annotations
import time
from typing import Any
from model_router.config import ModelRoutingConfig, load_model_routing_config
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider, OpenRouterProvider
from model_router.prompt_firewall import PromptFirewall
from model_router.tasks import ModelTask
from model_router.cost_tracker import CostTracker

_PROVIDER_CLASSES = {
    "deepseek_v4_flash": DeepSeekV4FlashProvider,
    "minimax_m3": MinimaxM3Provider,
    "mock": MockProvider,
}


class ModelRouter:
    def __init__(self, config_path: Any | None = None):
        self.config: ModelRoutingConfig = load_model_routing_config(config_path)
        self.providers: dict[str, Any] = {}
        self._init_providers()
        self.prompt_firewall = PromptFirewall(
            self.config.blocked_prompt_categories,
            self.config.secret_key_env_names,
        )
        self.cost_tracker = CostTracker()

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
            default = "deepseek_v4_flash"
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
        started = time.monotonic()
        try:
            if not self.config.live_model_calls_enabled:
                raise RuntimeError("live_model_calls_enabled is false")
            content_text, metadata = await provider.complete(sanitized, task, max_tokens, temperature)
        except Exception:
            if not self.config.mock_fallback_enabled:
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
