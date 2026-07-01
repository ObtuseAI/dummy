"""Hybrid model routing with DeepSeekV4Flash fast pass and MinimaxM3 critique."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from model_router.output_firewall import ModelOutputFirewall
from model_router.prompt_firewall import PromptFirewallV2
from model_router.router import ModelRouter
from model_router.tasks import ModelTask


class HybridModelResult(BaseModel):
    """Result of a fast/critique hybrid model route."""

    fast_envelope: dict[str, Any] | None = None
    critique_envelope: dict[str, Any] | None = None
    degraded: bool = False
    fallback: str = ""
    blocked_classification: str | None = None
    prompt_sanitized: str = ""
    output_blocked: list[dict[str, str]] = Field(default_factory=list)


class MeshHybridRouter:
    """Route a prompt through DeepSeekV4Flash and MinimaxM3 concurrently.

    - ``PromptFirewallV2`` gates the input.
    - ``ModelOutputFirewall`` gates both model outputs.
    - Any failure (blocked prompt, timeout, provider error, unsafe output)
      returns a deterministic fallback and marks the result as degraded.
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        prompt_firewall: PromptFirewallV2 | None = None,
        output_firewall: ModelOutputFirewall | None = None,
    ) -> None:
        self.router = router or ModelRouter()
        self.prompt_firewall = prompt_firewall or PromptFirewallV2()
        self.output_firewall = output_firewall or ModelOutputFirewall()

    async def route(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        timeout: float = 18.0,
        max_tokens: int = 512,
    ) -> HybridModelResult:
        """Run the hybrid pair and return a ``HybridModelResult``."""
        decision = self.prompt_firewall.block_check(prompt)
        if not decision.allowed:
            return HybridModelResult(
                degraded=True,
                fallback="prompt_blocked",
                blocked_classification=decision.classification,
            )

        sanitized = self.prompt_firewall.sanitize(prompt)

        try:
            fast_env, critique_env = await asyncio.wait_for(
                asyncio.gather(
                    self.router.call(
                        ModelTask.FORECAST_OPINION,
                        sanitized,
                        context=context,
                        max_tokens=max_tokens,
                    ),
                    self.router.call(
                        ModelTask.STRATEGY_CRITIQUE,
                        sanitized,
                        context=context,
                        max_tokens=max_tokens,
                    ),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return HybridModelResult(
                degraded=True,
                fallback="model_timeout",
                prompt_sanitized=sanitized,
            )
        except Exception as exc:
            return HybridModelResult(
                degraded=True,
                fallback=f"model_error: {type(exc).__name__}",
                prompt_sanitized=sanitized,
            )

        blocked: list[dict[str, str]] = []
        for label, env in (("fast", fast_env), ("critique", critique_env)):
            if env.blocked_by:
                blocked.append(
                    {"envelope": label, "category": env.blocked_by}
                )
                continue
            of_decision = self.output_firewall.check(env.content)
            if not of_decision.safe:
                blocked.extend(of_decision.blocked_patterns)

        if blocked:
            return HybridModelResult(
                degraded=True,
                fallback="output_blocked",
                prompt_sanitized=sanitized,
                output_blocked=blocked,
                fast_envelope=fast_env.model_dump(),
                critique_envelope=critique_env.model_dump(),
            )

        return HybridModelResult(
            degraded=False,
            prompt_sanitized=sanitized,
            fast_envelope=fast_env.model_dump(),
            critique_envelope=critique_env.model_dump(),
        )
