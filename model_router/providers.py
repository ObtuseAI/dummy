from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from model_router.config import ProviderConfig
from model_router.credential_source import ProviderCredentialSourceResolver
from model_router.error_classifier import (
    ProviderResponseSchemaError,
    classify_provider_error,
)
from model_router.network_capability import (
    ModelNetworkCapability,
    require_model_network_capability,
    validate_model_provider_endpoint,
)
from model_router.tasks import ModelTask


# Errors that are considered transient and should be retried with backoff.
_RETRYABLE_ERROR_CLASSES = {
    "TIMEOUT",
    "CONNECT_ERROR",
    "NETWORK_ERROR",
    "HTTP_429",
}


def _is_retryable(error_class: str | None) -> bool:
    if error_class in _RETRYABLE_ERROR_CLASSES:
        return True
    # Retry any HTTP 5xx server error regardless of exact status code.
    if error_class and error_class.startswith("HTTP_5"):
        return True
    return False

# Minimal required keys for the JSON responses produced by each task.  The
# provider validates the shape before returning so callers can rely on the
# content downstream.
_TASK_SCHEMAS: dict[ModelTask, set[str]] = {
    ModelTask.FORECAST_OPINION: {"dummy_probability", "confidence_score", "reasoning"},
    ModelTask.RAPID_FORECAST: {
        "dummy_probability",
        "confidence_score",
        "reasoning",
        "action",
        "entry_condition",
    },
    ModelTask.STRATEGY_CRITIQUE: {"verdict", "reasoning"},
    ModelTask.RISK_CRITIQUE: {"risk_level", "reasoning"},
    ModelTask.NO_TRADE_REASON: {"reason", "contributing_factors"},
    ModelTask.TRADE_DRAFT: {"action", "reasoning"},
    ModelTask.CALIBRATION_NOTE: {"note"},
    ModelTask.MARKET_THESIS: {"thesis", "confidence"},
    ModelTask.REFLECTION_LESSONS: {"lessons"},
    ModelTask.HYBRID_REVIEW: {"verdict", "agreement_score"},
}


@dataclass(frozen=True)
class _ProviderCallResult:
    """One request's content and telemetry, kept concurrency-local."""

    content: str
    usage: dict[str, int] | None = None
    actual_model: str | None = None


class ProviderError(Exception):
    """Raised when a provider exhausts all retry attempts.

    The attached ``metadata`` dict contains the same redacted fields a
    successful call would return (provider, model, latency_ms, attempts,
    prompt_digest, error_class, cost_usd).  It never contains the raw prompt
    or any API key.
    """

    def __init__(self, message: str, metadata: dict[str, Any]):
        super().__init__(message)
        self.metadata = metadata


def _prompt_digest(prompt: str) -> str:
    """Return the first 16 characters of the SHA-256 hash of *prompt*."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class BaseModelProvider(ABC):
    """Abstract base for live model provider adapters.

    Subclasses must implement :meth:`_call_api`.  The public :meth:`complete`
    method adds timeout configuration, retry/backoff, schema validation,
    latency measurement, and redacted metadata.
    """

    name: str = "base"
    # Which LLM backend switch gates this provider (None = ungated, e.g. mock).
    _backend: str | None = None
    # HTTP providers override this.  Mock and injected local-only providers do
    # not need a paid-network capability merely to exercise response handling.
    _network_capability_required = False

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def available(self) -> bool:
        from model_router.llm_switches import llm_backend_enabled

        if self._backend is not None and not llm_backend_enabled(self._backend):
            return False
        return bool(ProviderCredentialSourceResolver().resolve(self.config.api_key_env).present)

    @property
    def _model_name(self) -> str:
        """Concrete providers may override this to read environment variables."""
        return self.config.model_name

    @property
    def _api_base(self) -> str:
        return self.config.api_base

    @abstractmethod
    async def _call_api(
        self, prompt: str, task: ModelTask, max_tokens: int, temperature: float
    ) -> str | _ProviderCallResult:
        """Make a single provider API call and return the raw response text."""
        ...

    @staticmethod
    def _backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
        return base_delay * (2 ** attempt)

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown JSON fences some providers wrap around JSON output."""
        text = text.strip()
        if text.startswith("```"):
            # Drop the opening fence line (e.g. ```json)
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.strip()
        if text.endswith("```"):
            text = text.rsplit("\n", 1)[0]
            text = text.strip()
        return text

    def _validate_response(self, text: str, task: ModelTask) -> str:
        """Parse and validate the response JSON against the task schema.

        Raises:
            ProviderResponseSchemaError: if the text is not valid JSON or is
                missing required keys for *task*.
        """
        stripped = self._strip_markdown_fences(text)
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProviderResponseSchemaError(
                f"Provider response is not valid JSON: {exc}"
            ) from exc

        required = _TASK_SCHEMAS.get(task)
        if required:
            missing = required - set(data.keys() if isinstance(data, dict) else ())
            if missing:
                raise ProviderResponseSchemaError(
                    f"Response missing required fields for {task.value}: {sorted(missing)}"
                )
        if not isinstance(data, dict):
            raise ProviderResponseSchemaError(
                f"Response for {task.value} must be a JSON object"
            )

        def probability(value: Any) -> Decimal | None:
            if isinstance(value, bool):
                return None
            try:
                parsed = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return None
            if not parsed.is_finite() or not Decimal("0") <= parsed <= Decimal("1"):
                return None
            return parsed

        semantic_error: str | None = None
        if task in {ModelTask.FORECAST_OPINION, ModelTask.RAPID_FORECAST}:
            forecast_probability = probability(data.get("dummy_probability"))
            if forecast_probability is None:
                semantic_error = "dummy_probability must be finite and in [0, 1]"
            elif probability(data.get("confidence_score")) is None:
                semantic_error = "confidence_score must be finite and in [0, 1]"
            elif not isinstance(data.get("reasoning"), str) or not data["reasoning"].strip():
                semantic_error = "reasoning must be a non-empty string"
            elif "uncertainty_band" in data:
                band = data["uncertainty_band"]
                if not isinstance(band, list) or len(band) != 2:
                    semantic_error = "uncertainty_band must contain [low, high]"
                else:
                    low, high = probability(band[0]), probability(band[1])
                    if (
                        low is None
                        or high is None
                        or not low <= forecast_probability <= high
                    ):
                        semantic_error = (
                            "uncertainty_band must be ordered, finite, in [0, 1], "
                            "and contain dummy_probability"
                        )
            if semantic_error is None and task is ModelTask.RAPID_FORECAST:
                if str(data.get("action", "")).lower() not in {
                    "hold",
                    "consider_yes",
                    "consider_no",
                }:
                    semantic_error = (
                        "action must be hold, consider_yes, or consider_no"
                    )
                elif not isinstance(data.get("entry_condition"), str) or not data[
                    "entry_condition"
                ].strip():
                    semantic_error = "entry_condition must be a non-empty string"
        elif task is ModelTask.STRATEGY_CRITIQUE:
            if str(data.get("verdict", "")).lower() not in {
                "block",
                "warn",
                "proceed",
            }:
                semantic_error = "verdict must be proceed, warn, or block"
        elif task is ModelTask.RISK_CRITIQUE:
            if str(data.get("risk_level", "")).lower() not in {
                "low",
                "medium",
                "high",
                "critical",
            }:
                semantic_error = "risk_level must be low, medium, high, or critical"
        elif task is ModelTask.NO_TRADE_REASON:
            reason = data.get("reason")
            factors = data.get("contributing_factors")
            if reason is not None and not isinstance(reason, str):
                semantic_error = "reason must be a string or null"
            elif not isinstance(factors, list) or any(
                not isinstance(item, str) or not item.strip() for item in factors
            ):
                semantic_error = "contributing_factors must be a list of strings"
        elif task is ModelTask.MARKET_THESIS:
            if probability(data.get("confidence")) is None:
                semantic_error = "confidence must be finite and in [0, 1]"
        elif task is ModelTask.REFLECTION_LESSONS:
            lessons = data.get("lessons")
            if not isinstance(lessons, list) or any(
                not isinstance(item, str) or not item.strip() for item in lessons
            ):
                semantic_error = "lessons must be a list of non-empty strings"

        if semantic_error is not None:
            raise ProviderResponseSchemaError(
                f"Invalid {task.value} response: {semantic_error}"
            )
        return stripped

    def _estimate_cost(self, usage: dict[str, int] | None) -> float | None:
        """Estimate USD cost from token usage, if available.

        Returns ``None`` when no usage information is present.  Mock providers
        should override to return ``0.0``.
        """
        if usage is None:
            return None
        # Prefer config-pinned list prices so telemetry follows the exact
        # OpenRouter route rather than an unrelated generic estimate.
        model_pricing = {
            "deepseek/deepseek-v3": (0.50, 2.00),
            "minimax/minimax-01": (0.20, 1.10),
        }
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        configured = (
            self.config.prompt_cost_per_million,
            self.config.completion_cost_per_million,
        )
        if all(price is not None for price in configured):
            prompt_price, completion_price = configured
        else:
            prompt_price, completion_price = model_pricing.get(
                self._model_name, (1.00, 5.00)
            )
        return round(
            (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000,
            6,
        )

    async def complete(
        self,
        prompt: str,
        task: ModelTask,
        max_tokens: int = 512,
        temperature: float = 0.2,
        max_retries: int | None = None,
        *,
        network_capability: ModelNetworkCapability | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return ``(response_text, metadata)``.

        ``metadata`` always contains:
            - ``provider``: provider slug.
            - ``model``: model name actually used.
            - ``latency_ms``: elapsed time for the call.
            - ``attempts``: number of API attempts (including retries).
            - ``prompt_digest``: first 16 hex chars of SHA-256(prompt).
            - ``error_class``: ``None`` on success, otherwise a classifier tag.
            - ``cost_usd``: estimated cost when usage is reported, else ``None``.
        """
        # Enforce authority at the common public sink, not only in ModelRouter.
        # Direct provider calls therefore cannot bypass a disabled routing
        # config simply because a real key is discoverable in the project .env.
        if self._network_capability_required:
            require_model_network_capability(network_capability)

        started = time.monotonic()
        digest = _prompt_digest(prompt)
        last_exc: Exception | None = None
        error_class: str | None = None
        attempts = 0

        retry_limit = self.config.max_retries if max_retries is None else max_retries
        retry_limit = max(0, min(3, int(retry_limit)))
        for attempt in range(retry_limit + 1):
            attempts += 1
            try:
                raw_result = await self._call_api(
                    prompt, task, max_tokens, temperature
                )
                if isinstance(raw_result, _ProviderCallResult):
                    text = raw_result.content
                    usage = raw_result.usage
                    actual_model = raw_result.actual_model or self._model_name
                else:
                    # Compatibility for local/mock/test providers whose
                    # low-level method still returns only content.
                    text = raw_result
                    usage = None
                    actual_model = self._model_name
                text = self._validate_response(text, task)
                latency_ms = (time.monotonic() - started) * 1000
                metadata: dict[str, Any] = {
                    "provider": self.name,
                    "model": actual_model,
                    "latency_ms": round(latency_ms, 4),
                    "attempts": attempts,
                    "prompt_digest": digest,
                    "error_class": None,
                    "cost_usd": self._estimate_cost(usage),
                }
                return text, metadata
            except Exception as exc:
                last_exc = exc
                error_class = classify_provider_error(exc)
                if not _is_retryable(error_class):
                    break
                if attempt < retry_limit:
                    await asyncio.sleep(self._backoff_delay(attempt))

        latency_ms = (time.monotonic() - started) * 1000
        metadata = {
            "provider": self.name,
            "model": self._model_name,
            "latency_ms": round(latency_ms, 4),
            "attempts": attempts,
            "prompt_digest": digest,
            "error_class": error_class,
            "cost_usd": None,
        }
        raise ProviderError(str(last_exc), metadata=metadata) from last_exc


class _OpenAICompatibleProvider(BaseModelProvider):
    """Mixin for providers that speak the OpenAI-compatible chat completions API."""

    _timeout_seconds: float | None = None
    _backend = "openrouter"   # gated by the openrouter LLM switch
    _network_capability_required = True

    async def _call_api(
        self, prompt: str, task: ModelTask, max_tokens: int, temperature: float
    ) -> str | _ProviderCallResult:
        # Validate the host/key binding before reading the secret.  In
        # particular, legacy DEEPSEEK_BASE_URL/MINIMAX_BASE_URL overrides may
        # never redirect an OpenRouter bearer token to another host.
        validate_model_provider_endpoint(self._api_base, self.config.api_key_env)
        credential_resolver = ProviderCredentialSourceResolver()
        key = credential_resolver.get_value(self.config.api_key_env)
        if not key:
            raise RuntimeError(f"{self.config.api_key_env} not set")

        body: dict[str, Any] = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.config.reasoning_effort:
            # OpenRouter's unified reasoning object is portable across Google,
            # OpenAI, Anthropic, and compatible reasoning models.
            body["reasoning"] = {"effort": self.config.reasoning_effort}
        # Some provider/model combos on OpenRouter do not accept json_object response_format.
        if not ("openrouter" in self._api_base.lower() and "minimax" in self._model_name.lower()):
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if "openrouter" in self._api_base.lower():
            headers["HTTP-Referer"] = "https://dummy.local"
            headers["X-Title"] = "Dummy"

        timeout = self._timeout_seconds if self._timeout_seconds is not None else self.config.timeout_seconds
        async with httpx.AsyncClient(timeout=min(timeout, 20)) as client:
            r = await client.post(
                f"{self._api_base.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=body,
            )
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage")
        actual_model = data.get("model")
        if self.name == "openrouter_generic":
            if not isinstance(actual_model, str) or not actual_model.strip():
                raise ProviderResponseSchemaError(
                    "OpenRouter response omitted the actual model identity"
                )
            if actual_model != self._model_name:
                raise ProviderResponseSchemaError(
                    "OpenRouter returned a model other than the configured exact route"
                )
        return _ProviderCallResult(
            content=content,
            usage=usage if isinstance(usage, dict) else None,
            actual_model=(
                actual_model
                if self.name == "openrouter_generic" and isinstance(actual_model, str)
                else self._model_name
            ),
        )


class DeepSeekV4FlashProvider(_OpenAICompatibleProvider):
    name = "deepseek_v4_flash"

    @property
    def _api_base(self) -> str:
        return (
            os.environ.get("DEEPSEEK_BASE_URL")
            or self.config.api_base
            or "https://api.deepseek.com"
        )

    @property
    def _model_name(self) -> str:
        return (
            os.environ.get("DEEPSEEK_MODEL")
            or self.config.model_name
            or "deepseekv4flash"
        )


class MinimaxM3Provider(_OpenAICompatibleProvider):
    name = "minimax_m3"

    @property
    def _api_base(self) -> str:
        return (
            os.environ.get("MINIMAX_BASE_URL")
            or self.config.api_base
            or "https://api.minimax.chat"
        )

    @property
    def _model_name(self) -> str:
        return (
            os.environ.get("MINIMAX_MODEL")
            or self.config.model_name
            or "minimaxm3"
        )


class OpenRouterProvider(_OpenAICompatibleProvider):
    """Generic OpenRouter-backed model. Reads api_base/model_name from config,
    so the routing config can add any model (Claude, GPT, Gemini, Llama, ...)
    for the debate panel without new code."""

    name = "openrouter_generic"


class MockProvider(BaseModelProvider):
    name = "mock"

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(
            config
            or ProviderConfig(api_base="", api_key_env="", model_name="mock")
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def _model_name(self) -> str:
        return "mock"

    async def _call_api(
        self, prompt: str, task: ModelTask, max_tokens: int, temperature: float
    ) -> str:
        deterministic: dict[ModelTask, str] = {
            ModelTask.FORECAST_OPINION: json.dumps(
                {
                    "dummy_probability": "0.55",
                    "confidence_score": "0.72",
                    "reasoning": "mock forecast",
                }
            ),
            ModelTask.RAPID_FORECAST: json.dumps(
                {
                    "dummy_probability": "0.55",
                    "confidence_score": "0.72",
                    "reasoning": "mock rapid forecast",
                    "action": "hold",
                    "entry_condition": "mock only; never submit",
                }
            ),
            ModelTask.STRATEGY_CRITIQUE: json.dumps(
                {"verdict": "proceed", "reasoning": "mock critique"}
            ),
            ModelTask.RISK_CRITIQUE: json.dumps(
                {"risk_level": "low", "reasoning": "mock risk critique"}
            ),
            ModelTask.NO_TRADE_REASON: json.dumps(
                {
                    "reason": "mock no-trade",
                    "contributing_factors": ["mock"],
                }
            ),
            ModelTask.TRADE_DRAFT: json.dumps(
                {"action": "hold", "reasoning": "mock trade draft"}
            ),
            ModelTask.CALIBRATION_NOTE: json.dumps({"note": "mock calibration"}),
            ModelTask.MARKET_THESIS: json.dumps(
                {"thesis": "mock thesis", "confidence": "0.60"}
            ),
            ModelTask.REFLECTION_LESSONS: json.dumps(
                {"lessons": ["mock reflection; never operationalize"]}
            ),
            ModelTask.HYBRID_REVIEW: json.dumps(
                {"verdict": "agree", "agreement_score": "0.80"}
            ),
        }
        return deterministic.get(task, json.dumps({"note": "mock response"}))

    def _estimate_cost(self, usage: dict[str, int] | None) -> float | None:
        return 0.0
