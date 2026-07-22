"""Hybrid model routing with DeepSeekV4Flash fast pass and MinimaxM3 critique."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from pydantic import BaseModel, Field

from model_router.output_firewall import ModelOutputFirewall
from model_router.prompt_firewall import PromptFirewallV2
from model_router.router import ModelRouter
from model_router.tasks import ModelTask


def _redacted_envelope(block_reason: str, content: str) -> dict[str, Any]:
    """Return a safe placeholder for a blocked model output envelope.

    The raw envelope (which may contain blocked content or secrets) is replaced
    by a minimal digest plus the block reason so that downstream logs and
    artifacts never serialize unsafe output.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return {
        "blocked": True,
        "block_reason": block_reason,
        "digest": digest,
    }


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
        forecast_prompt = (
            sanitized
            + "\nReturn STRICT JSON with keys dummy_probability (0..1), "
            "confidence_score (0..1), reasoning (non-empty string), and optional "
            "uncertainty_band [low, high]."
        )
        critique_prompt = (
            sanitized
            + "\nAct as an independent strategy critic. Return STRICT JSON with "
            "keys verdict (proceed/warn/block) and reasoning (non-empty string)."
        )

        try:
            fast_env, critique_env = await asyncio.wait_for(
                asyncio.gather(
                    self.router.call(
                        ModelTask.FORECAST_OPINION,
                        forecast_prompt,
                        context=context,
                        max_tokens=max_tokens,
                    ),
                    self.router.call(
                        ModelTask.STRATEGY_CRITIQUE,
                        critique_prompt,
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
        fast_reason: str | None = None
        critique_reason: str | None = None
        for label, env in (("fast", fast_env), ("critique", critique_env)):
            expected_task = (
                ModelTask.FORECAST_OPINION
                if label == "fast"
                else ModelTask.STRATEGY_CRITIQUE
            )
            decision = getattr(env, "decision", None)
            config = getattr(self.router, "config", None)
            expected_provider = (
                config.default_provider.get(expected_task.value)
                if config is not None
                else None
            )
            if (
                getattr(env, "task", None) != expected_task
                or decision is None
                or getattr(decision, "task", None) != expected_task
                or getattr(decision, "fallback_reason", None)
                or getattr(decision, "provider_name", None) in {"mock", "none"}
                or (
                    expected_provider is not None
                    and getattr(decision, "provider_name", None) != expected_provider
                )
            ):
                return HybridModelResult(
                    degraded=True,
                    fallback=f"route_contract_invalid:{label}",
                    prompt_sanitized=sanitized,
                )
            if env.blocked_by:
                reason = env.blocked_by
                blocked.append({"envelope": label, "category": reason})
                if label == "fast":
                    fast_reason = reason
                else:
                    critique_reason = reason
                continue
            of_decision = self.output_firewall.check(env.content)
            if not of_decision.safe:
                reason = of_decision.blocked_patterns[0]["category"]
                blocked.extend(of_decision.blocked_patterns)
                if label == "fast":
                    fast_reason = reason
                else:
                    critique_reason = reason

        if blocked:
            fast_out = (
                fast_env.model_dump()
                if fast_reason is None
                else _redacted_envelope(fast_reason, fast_env.content)
            )
            critique_out = (
                critique_env.model_dump()
                if critique_reason is None
                else _redacted_envelope(critique_reason, critique_env.content)
            )
            return HybridModelResult(
                degraded=True,
                fallback="output_blocked",
                prompt_sanitized=sanitized,
                output_blocked=blocked,
                fast_envelope=fast_out,
                critique_envelope=critique_out,
            )

        return HybridModelResult(
            degraded=False,
            prompt_sanitized=sanitized,
            fast_envelope=fast_env.model_dump(),
            critique_envelope=critique_env.model_dump(),
        )
