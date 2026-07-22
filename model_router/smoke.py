from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model_router.config import ProviderConfig, load_model_routing_config
from model_router.credential_source import (
    ProviderCredentialReadinessV2,
    ProviderCredentialSourceResolver,
)
from model_router.credential_readiness import CredentialReadiness
from model_router.output_firewall import ModelOutputFirewall
from model_router.network_capability import issue_model_network_capability
from model_router.prompt_firewall import PromptFirewallV2
from model_router.providers import (
    BaseModelProvider,
    DeepSeekV4FlashProvider,
    MinimaxM3Provider,
    MockProvider,
    ProviderError,
)
from model_router.tasks import ModelTask
from model_router.resolver import (
    ModelProviderResolver,
    ProviderResolutionResult,
    _DEFAULT_ALIASES,
    _DEFAULT_BASE_URLS,
)
from model_router.route_mode import ProviderRouteMode, ProviderRouteModeResolver


ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts" / "dummy"

SMOKE_CALL_TIMEOUT = 20
SMOKE_TOTAL_TIMEOUT = 45


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_digest(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


# Harmless smoke prompts.  They contain no account data, secrets, or order
# instructions and are designed to pass PromptFirewallV2 as safe market prompts.
_DEEPSEEK_SMOKE_PROMPT = (
    "Provide a concise neutral market summary in one or two sentences. "
    "Return only a JSON object with keys 'thesis' and 'confidence'. "
    "Do not include account data, secrets, order instructions, or trading actions."
)

_MINIMAX_SMOKE_PROMPT = (
    "Provide a concise risk critique of broad market conditions. "
    "Return only a JSON object with keys 'risk_level' and 'reasoning'. "
    "Do not include account data, secrets, order instructions, or trading actions."
)


@dataclass
class SmokeCallResult:
    provider: str
    model: str
    task: str
    latency_ms: float
    attempts: int
    prompt_digest: str
    prompt_summary: str
    response_schema_ok: bool
    firewall_ok: bool
    order_instruction_free: bool
    secret_free: bool
    error_class: str | None
    status: str
    error: str | None = None
    output_firewall_ok: bool = True
    response_text: str = ""


class LiveModelSmoke:
    """Run a live-model smoke test for DeepSeekV4Flash and MinimaxM3.

    This retired runner defaults to local preflight mode even when credentials
    are present. A direct manual caller must pass ``allow_live=True`` to permit
    provider contact. Missing credentials still fall back to ``MockProvider``.
    No raw API keys or raw prompts are ever written to reports.
    """

    def __init__(
        self,
        deepseek_prompt: str | None = None,
        minimax_prompt: str | None = None,
        artifacts_dir: Path | None = None,
        *,
        allow_live: bool = False,
    ):
        self.deepseek_prompt = deepseek_prompt or _DEEPSEEK_SMOKE_PROMPT
        self.minimax_prompt = minimax_prompt or _MINIMAX_SMOKE_PROMPT
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.firewall = PromptFirewallV2()
        self.credential_readiness = CredentialReadiness()
        # This module is legacy/archive tooling.  Credential presence must
        # never turn an ordinary report generation or dashboard read into a
        # provider call.  Only a direct manual caller that passes the explicit
        # keyword flag may authorize network contact.
        self.live_contact_authorized = allow_live is True

    def _build_provider(self, name: str) -> BaseModelProvider:
        cfg = load_model_routing_config()
        configs = cfg.provider_configs
        if name == "deepseek_v4_flash" and "deepseek_v4_flash" in configs:
            return DeepSeekV4FlashProvider(configs["deepseek_v4_flash"])
        if name == "minimax_m3" and "minimax_m3" in configs:
            return MinimaxM3Provider(configs["minimax_m3"])

        # Fallback to environment-driven config if routing config is incomplete.
        if name == "deepseek_v4_flash":
            return DeepSeekV4FlashProvider(
                ProviderConfig(
                    api_base=os.environ.get(
                        "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                    ),
                    api_key_env="DEEPSEEK_API_KEY",
                    model_name=os.environ.get("DEEPSEEK_MODEL", "deepseekv4flash"),
                )
            )
        return MinimaxM3Provider(
            ProviderConfig(
                api_base=os.environ.get(
                    "MINIMAX_BASE_URL", "https://api.minimax.chat"
                ),
                api_key_env="MINIMAX_API_KEY",
                model_name=os.environ.get("MINIMAX_MODEL", "minimaxm3"),
            )
        )

    def _response_schema_ok(self, text: str, task: ModelTask) -> bool:
        """Validate that *text* parses and contains the required keys for *task*."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False

        required: set[str] | None = None
        if task is ModelTask.MARKET_THESIS:
            required = {"thesis", "confidence"}
        elif task is ModelTask.RISK_CRITIQUE:
            required = {"risk_level", "reasoning"}
        if required:
            return required.issubset(set(data.keys()) if isinstance(data, dict) else ())
        return True

    def _order_instruction_free(self, text: str) -> bool:
        decision = self.firewall.block_check(text)
        return decision.classification != "ORDER_INSTRUCTION_BLOCK"

    def _secret_free(self, text: str) -> bool:
        """Return True when *text* contains no credential-like material.

        Whitespace normalization in ``sanitize`` is ignored so that harmless
        JSON responses with line breaks do not false-positive.
        """
        import re

        sanitized = self.firewall.sanitize(text)
        normalized = re.sub(r"\s+", " ", text).strip()
        return sanitized == normalized

    async def _execute_call(
        self,
        provider: BaseModelProvider,
        prompt: str,
        task: ModelTask,
        prompt_summary: str,
        output_firewall_check=None,
    ) -> SmokeCallResult:
        if not self.live_contact_authorized and not isinstance(provider, MockProvider):
            # Guard the lowest-level call site as well as the public runners so
            # a future caller cannot bypass the opt-in by invoking this helper.
            provider = MockProvider()

        sanitized = self.firewall.sanitize(prompt)
        decision = self.firewall.block_check(sanitized)
        digest = _sha256_digest(prompt)

        if not decision.allowed:
            return SmokeCallResult(
                provider=provider.name,
                model=getattr(provider, "_model_name", "unknown"),
                task=task.value,
                latency_ms=0.0,
                attempts=0,
                prompt_digest=digest,
                prompt_summary=prompt_summary,
                response_schema_ok=False,
                firewall_ok=False,
                order_instruction_free=False,
                secret_free=False,
                error_class="FIREWALL_BLOCK",
                status="firewall_block",
                error=f"prompt blocked: {decision.classification}",
                output_firewall_ok=True,
            )

        try:
            network_capability = (
                issue_model_network_capability(
                    allow_live=self.live_contact_authorized,
                    source="legacy_live_model_smoke",
                )
                if not isinstance(provider, MockProvider)
                else None
            )
            text, metadata = await asyncio.wait_for(
                provider.complete(
                    sanitized,
                    task,
                    max_tokens=256,
                    temperature=0.2,
                    network_capability=network_capability,
                ),
                timeout=SMOKE_CALL_TIMEOUT,
            )
        except (asyncio.TimeoutError, ProviderError) as exc:
            # On timeout or provider failure, fall back to MockProvider for this
            # provider only and mark the call as a mock fallback.
            if isinstance(exc, asyncio.TimeoutError):
                error_class = "TIMEOUT"
                error_msg = "provider smoke call timed out"
            else:
                error_class = exc.metadata.get("error_class", "PROVIDER_ERROR")
                error_msg = str(exc)
            mock = MockProvider()
            text, metadata = await mock.complete(sanitized, task, max_tokens=256, temperature=0.2)
            return SmokeCallResult(
                provider=provider.name,
                model=getattr(provider, "_model_name", "unknown"),
                task=task.value,
                latency_ms=metadata.get("latency_ms", 0.0),
                attempts=metadata.get("attempts", 0),
                prompt_digest=digest,
                prompt_summary=prompt_summary,
                response_schema_ok=self._response_schema_ok(text, task),
                firewall_ok=True,
                order_instruction_free=self._order_instruction_free(text),
                secret_free=self._secret_free(text),
                error_class=error_class,
                status="mock_fallback",
                error=error_msg,
                output_firewall_ok=(output_firewall_check(text) if output_firewall_check else True),
                response_text=text,
            )

        schema_ok = self._response_schema_ok(text, task)
        order_free = self._order_instruction_free(text)
        secret_free = self._secret_free(text)
        output_safe = output_firewall_check(text) if output_firewall_check else True
        return SmokeCallResult(
            provider=metadata.get("provider", provider.name),
            model=metadata.get("model", "unknown"),
            task=task.value,
            latency_ms=metadata.get("latency_ms", 0.0),
            attempts=metadata.get("attempts", 0),
            prompt_digest=metadata.get("prompt_digest", digest),
            prompt_summary=prompt_summary,
            response_schema_ok=schema_ok,
            firewall_ok=True,
            order_instruction_free=order_free,
            secret_free=secret_free,
            error_class=None,
            status="ok",
            output_firewall_ok=output_safe,
            response_text=text,
        )

    def _result_to_dict(self, result: SmokeCallResult) -> dict[str, Any]:
        return {
            "provider": result.provider,
            "model": result.model,
            "task": result.task,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_digest": result.prompt_digest,
            "prompt_summary": result.prompt_summary,
            "response_schema_ok": result.response_schema_ok,
            "firewall_ok": result.firewall_ok,
            "output_firewall_ok": result.output_firewall_ok,
            "order_instruction_free": result.order_instruction_free,
            "secret_free": result.secret_free,
            "error_class": result.error_class,
            "status": result.status,
        }

    async def _run_inner(self) -> dict[str, Any]:
        """Body of :meth:`run` without the total-timeout wrapper."""
        ds_status = self.credential_readiness.deepseek_status()
        mm_status = self.credential_readiness.minimax_status()
        credentials_ready = self.credential_readiness.ready()
        ready = credentials_ready and self.live_contact_authorized

        results: list[SmokeCallResult] = []
        if ready:
            results.append(
                await self._execute_call(
                    self._build_provider("deepseek_v4_flash"),
                    self.deepseek_prompt,
                    ModelTask.MARKET_THESIS,
                    prompt_summary="harmless market summary prompt",
                )
            )
            results.append(
                await self._execute_call(
                    self._build_provider("minimax_m3"),
                    self.minimax_prompt,
                    ModelTask.RISK_CRITIQUE,
                    prompt_summary="harmless risk critique prompt",
                )
            )
        else:
            mock = MockProvider()
            results.append(
                await self._execute_call(
                    mock,
                    self.deepseek_prompt,
                    ModelTask.MARKET_THESIS,
                    prompt_summary="harmless market summary prompt",
                )
            )
            results.append(
                await self._execute_call(
                    mock,
                    self.minimax_prompt,
                    ModelTask.RISK_CRITIQUE,
                    prompt_summary="harmless risk critique prompt",
                )
            )

        any_fallback = any(r.status == "mock_fallback" for r in results)
        all_ok = all(
            r.status in ("ok", "mock_fallback")
            and r.response_schema_ok
            and r.firewall_ok
            and r.order_instruction_free
            and r.secret_free
            for r in results
        )
        live_model_status = "LIVE" if (ready and all_ok and not any_fallback) else "MOCK_ONLY"
        model_mode = "MOCK_ONLY" if (not ready or any_fallback) else "LIVE"

        if not ready:
            verdict = "PASS"
        elif any_fallback:
            verdict = "PASS"
        else:
            verdict = "PASS" if all_ok else "FAIL"

        return {
            "generated_at": _now_iso(),
            "workstream": "V8: Live Model Smoke",
            "live_model_status": live_model_status,
            "model_mode": model_mode,
            "credential_status": {
                "deepseek": ds_status.as_dict(),
                "minimax": mm_status.as_dict(),
                "all_ready": credentials_ready,
            },
            "live_contact_authorized": self.live_contact_authorized,
            "contact_mode": "LIVE_MANUAL" if self.live_contact_authorized else "PREFLIGHT_ONLY",
            "call_results": [self._result_to_dict(r) for r in results],
            "verdict": verdict,
        }

    async def run(self) -> dict[str, Any]:
        """Run smoke calls and return a redacted report dict.

        The returned dict contains ``live_model_status`` (``"LIVE"`` only when
        both credentials are present, manual live contact was authorized, and
        every smoke call succeeds) and ``model_mode`` (``"LIVE"`` only for
        that explicitly authorized path, ``"MOCK_ONLY"`` otherwise).

        A hard total timeout guarantees the smoke runner cannot block the
        caller indefinitely, even if both provider calls stall.
        """
        try:
            return await asyncio.wait_for(self._run_inner(), timeout=SMOKE_TOTAL_TIMEOUT)
        except asyncio.TimeoutError:
            mock = MockProvider()
            ds_status = self.credential_readiness.deepseek_status()
            mm_status = self.credential_readiness.minimax_status()
            credentials_ready = self.credential_readiness.ready()
            results = []
            for prompt, task, summary in (
                (self.deepseek_prompt, ModelTask.MARKET_THESIS, "harmless market summary prompt"),
                (self.minimax_prompt, ModelTask.RISK_CRITIQUE, "harmless risk critique prompt"),
            ):
                text, metadata = await mock.complete(prompt, task, max_tokens=256, temperature=0.2)
                results.append(
                    SmokeCallResult(
                        provider="mock",
                        model="mock",
                        task=task.value,
                        latency_ms=metadata.get("latency_ms", 0.0),
                        attempts=metadata.get("attempts", 0),
                        prompt_digest=_sha256_digest(prompt),
                        prompt_summary=summary,
                        response_schema_ok=self._response_schema_ok(text, task),
                        firewall_ok=True,
                        order_instruction_free=self._order_instruction_free(text),
                        secret_free=self._secret_free(text),
                        error_class="TIMEOUT",
                        status="mock_fallback",
                        error="smoke runner total timeout exceeded",
                    )
                )
            return {
                "generated_at": _now_iso(),
                "workstream": "V8: Live Model Smoke",
                "live_model_status": "MOCK_ONLY",
                "model_mode": "MOCK_ONLY",
                "credential_status": {
                    "deepseek": ds_status.as_dict(),
                    "minimax": mm_status.as_dict(),
                    "all_ready": credentials_ready,
                },
                "live_contact_authorized": self.live_contact_authorized,
                "contact_mode": "LIVE_MANUAL" if self.live_contact_authorized else "PREFLIGHT_ONLY",
                "call_results": [self._result_to_dict(r) for r in results],
                "verdict": "PASS",
                "note": f"smoke runner timed out after {SMOKE_TOTAL_TIMEOUT}s and fell back to mock",
            }

    def generate_prompt_safety_report(self) -> dict[str, Any]:
        """Return a report on prompt firewall safety for the smoke prompts."""
        prompts = [
            ("deepseek", self.deepseek_prompt, ModelTask.MARKET_THESIS.value),
            ("minimax", self.minimax_prompt, ModelTask.RISK_CRITIQUE.value),
        ]

        entries: list[dict[str, Any]] = []
        all_allowed = True
        for provider_name, prompt, task in prompts:
            sanitized = self.firewall.sanitize(prompt)
            decision = self.firewall.block_check(sanitized)
            if not decision.allowed:
                all_allowed = False
            entries.append(
                {
                    "provider": provider_name,
                    "task": task,
                    "prompt_digest": _sha256_digest(prompt),
                    "prompt_summary": "harmless market summary prompt"
                    if provider_name == "deepseek"
                    else "harmless risk critique prompt",
                    "firewall_classification": decision.classification,
                    "allowed": decision.allowed,
                    "matched_tokens": decision.matched_tokens,
                }
            )

        return {
            "generated_at": _now_iso(),
            "workstream": "V8: Live Model Prompt Safety",
            "prompt_entries": entries,
            "verdict": "PASS" if all_allowed else "FAIL",
        }

    def write_reports(
        self,
        smoke_report: dict[str, Any] | None = None,
        safety_report: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """Write smoke and prompt-safety reports to ``artifacts/dummy/``.

        Returns a mapping of report filename to written path.
        """
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        smoke = smoke_report or {"generated_at": _now_iso(), "workstream": "V8: Live Model Smoke"}
        smoke_path = self.artifacts_dir / "live_model_smoke_report_v1.json"
        smoke_path.write_text(json.dumps(smoke, indent=2, default=str))
        paths["live_model_smoke_report_v1.json"] = smoke_path

        safety = safety_report or self.generate_prompt_safety_report()
        safety_path = self.artifacts_dir / "live_model_prompt_safety_report_v1.json"
        safety_path.write_text(json.dumps(safety, indent=2, default=str))
        paths["live_model_prompt_safety_report_v1.json"] = safety_path

        return paths


async def generate_live_model_smoke_report_v1(*, allow_live: bool = False) -> dict[str, Any]:
    """Generate the legacy report; live contact requires explicit manual opt-in."""
    smoke = LiveModelSmoke(allow_live=allow_live)
    return await smoke.run()


def generate_live_model_prompt_safety_report_v1() -> dict[str, Any]:
    """Public helper used by the V8 report generation script."""
    smoke = LiveModelSmoke()
    return smoke.generate_prompt_safety_report()


# -----------------------------------------------------------------------------
# V8.1: resolved live-model smoke with explicit status labels
# -----------------------------------------------------------------------------

class LiveModelSmokeV2(LiveModelSmoke):
    """V8.1 smoke runner that resolves provider/model IDs before live calls.

    Status semantics:
      - LIVE_PROVEN: resolution + live call succeeded.
      - OPERATOR_MODEL_CONFIG_REQUIRED: model/endpoint could not be resolved.
      - PROVIDER_AUTH_FAILED: credentials were rejected.
      - MOCK_ONLY: credentials absent.

    All provider/model resolution is skipped unless ``allow_live=True`` was
    passed explicitly by a direct manual caller.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resolver = ModelProviderResolver()
        self.output_firewall = ModelOutputFirewall()

    def _build_resolved_provider(
        self, name: str, resolved_model: str, api_base: str, api_key_env: str | None = None
    ) -> BaseModelProvider:
        cfg = load_model_routing_config()
        configs = cfg.provider_configs
        if name == "deepseek_v4_flash":
            base_cfg = configs.get("deepseek_v4_flash") or ProviderConfig(
                api_base=api_base,
                api_key_env=api_key_env or "DEEPSEEK_API_KEY",
                model_name=resolved_model,
            )
            return DeepSeekV4FlashProvider(
                base_cfg.model_copy(update={"api_base": api_base, "api_key_env": api_key_env or base_cfg.api_key_env, "model_name": resolved_model})
            )
        base_cfg = configs.get("minimax_m3") or ProviderConfig(
            api_base=api_base,
            api_key_env=api_key_env or "MINIMAX_API_KEY",
            model_name=resolved_model,
        )
        return MinimaxM3Provider(
            base_cfg.model_copy(update={"api_base": api_base, "api_key_env": api_key_env or base_cfg.api_key_env, "model_name": resolved_model})
        )

    def _output_safe(self, text: str) -> bool:
        return self.output_firewall.check(text).safe

    async def _run_provider(
        self,
        name: str,
        prompt: str,
        task: ModelTask,
        prompt_summary: str,
    ) -> dict[str, Any]:
        if not self.live_contact_authorized:
            mock = MockProvider()
            text, metadata = await mock.complete(prompt, task, max_tokens=256, temperature=0.2)
            return {
                "provider": name,
                "model": "mock",
                "task": task.value,
                "status": "MOCK_ONLY",
                "latency_ms": metadata.get("latency_ms", 0.0),
                "attempts": metadata.get("attempts", 0),
                "prompt_digest": _sha256_digest(prompt),
                "prompt_summary": prompt_summary,
                "response_schema_ok": self._response_schema_ok(text, task),
                "prompt_firewall_ok": True,
                "output_firewall_ok": self._output_safe(text),
                "order_instruction_free": self._order_instruction_free(text),
                "secret_free": self._secret_free(text),
                "error_class": None,
                "contact_mode": "PREFLIGHT_ONLY",
            }

        network_capability = issue_model_network_capability(
            allow_live=self.live_contact_authorized,
            source="legacy_live_model_smoke_v2_resolver",
        )
        resolution = await self.resolver.resolve(
            name,
            default_base=_DEFAULT_BASE_URLS.get(name),
            default_aliases=_DEFAULT_ALIASES.get(name, []),
            smoke_prompt=prompt,
            allow_live=True,
            network_capability=network_capability,
        )

        if resolution.status == "MOCK_ONLY":
            mock = MockProvider()
            text, metadata = await mock.complete(prompt, task, max_tokens=256, temperature=0.2)
            return {
                "provider": name,
                "model": "mock",
                "task": task.value,
                "status": "MOCK_ONLY",
                "latency_ms": metadata.get("latency_ms", 0.0),
                "attempts": metadata.get("attempts", 0),
                "prompt_digest": _sha256_digest(prompt),
                "prompt_summary": prompt_summary,
                "response_schema_ok": self._response_schema_ok(text, task),
                "prompt_firewall_ok": True,
                "output_firewall_ok": self._output_safe(text),
                "order_instruction_free": self._order_instruction_free(text),
                "secret_free": self._secret_free(text),
                "error_class": None,
            }

        if resolution.status != "LIVE_PROVEN":
            return {
                "provider": name,
                "model": resolution.configured_model,
                "task": task.value,
                "status": resolution.status,
                "latency_ms": 0.0,
                "attempts": 0,
                "prompt_digest": _sha256_digest(prompt),
                "prompt_summary": prompt_summary,
                "response_schema_ok": False,
                "prompt_firewall_ok": True,
                "output_firewall_ok": True,
                "order_instruction_free": True,
                "secret_free": True,
                "error_class": resolution.error_category,
                "error_detail": resolution.error_detail,
            }

        provider = self._build_resolved_provider(
            name,
            resolution.resolved_model or resolution.configured_model,
            resolution.api_base,
            api_key_env=resolution.api_key_env,
        )
        result = await self._execute_call(
            provider,
            prompt,
            task,
            prompt_summary,
            output_firewall_check=self._output_safe,
        )
        return {
            "provider": name,
            "model": resolution.resolved_model or resolution.configured_model,
            "task": task.value,
            "status": "LIVE_PROVEN",
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_digest": result.prompt_digest,
            "prompt_summary": result.prompt_summary,
            "response_schema_ok": result.response_schema_ok,
            "prompt_firewall_ok": result.firewall_ok,
            "output_firewall_ok": result.output_firewall_ok,
            "order_instruction_free": result.order_instruction_free,
            "secret_free": result.secret_free,
            "error_class": result.error_class,
        }

    async def run(self) -> dict[str, Any]:
        """Run resolved smoke calls for DeepSeek and Minimax."""
        ds_result = await self._run_provider(
            "deepseek_v4_flash",
            self.deepseek_prompt,
            ModelTask.MARKET_THESIS,
            "harmless market summary prompt",
        )
        mm_result = await self._run_provider(
            "minimax_m3",
            self.minimax_prompt,
            ModelTask.RISK_CRITIQUE,
            "harmless risk critique prompt",
        )

        results = [ds_result, mm_result]
        proven = [r for r in results if r["status"] == "LIVE_PROVEN"]
        auth_failed = any(r["status"] == "PROVIDER_AUTH_FAILED" for r in results)
        config_required = any(r["status"] == "OPERATOR_MODEL_CONFIG_REQUIRED" for r in results)
        mock_only = all(r["status"] == "MOCK_ONLY" for r in results)

        if proven:
            live_model_status = "LIVE_PROVEN"
        elif auth_failed:
            live_model_status = "PROVIDER_AUTH_FAILED"
        elif config_required:
            live_model_status = "OPERATOR_MODEL_CONFIG_REQUIRED"
        elif mock_only:
            live_model_status = "MOCK_ONLY"
        else:
            live_model_status = "OPERATOR_MODEL_CONFIG_REQUIRED"

        all_safe = all(
            r["prompt_firewall_ok"] and r["output_firewall_ok"] and r["secret_free"]
            for r in results
        )
        verdict = "PASS" if all_safe else "FAIL"

        return {
            "generated_at": _now_iso(),
            "workstream": "V8.1: Live Model Smoke",
            "live_model_status": live_model_status,
            "model_mode": live_model_status,
            "call_results": results,
            "verdict": verdict,
            "live_contact_authorized": self.live_contact_authorized,
            "contact_mode": "LIVE_MANUAL" if self.live_contact_authorized else "PREFLIGHT_ONLY",
        }

    def generate_prompt_safety_report_v2(self) -> dict[str, Any]:
        """V8.1 prompt safety report with explicit provider labels."""
        prompts = [
            ("deepseek_v4_flash", self.deepseek_prompt, ModelTask.MARKET_THESIS.value),
            ("minimax_m3", self.minimax_prompt, ModelTask.RISK_CRITIQUE.value),
        ]
        entries = []
        all_allowed = True
        for provider_name, prompt, task in prompts:
            sanitized = self.firewall.sanitize(prompt)
            decision = self.firewall.block_check(sanitized)
            if not decision.allowed:
                all_allowed = False
            entries.append(
                {
                    "provider": provider_name,
                    "task": task,
                    "prompt_digest": _sha256_digest(prompt),
                    "prompt_summary": (
                        "harmless market summary prompt"
                        if provider_name == "deepseek_v4_flash"
                        else "harmless risk critique prompt"
                    ),
                    "firewall_classification": decision.classification,
                    "allowed": decision.allowed,
                    "matched_tokens": decision.matched_tokens,
                }
            )
        return {
            "generated_at": _now_iso(),
            "workstream": "V8.1: Live Model Prompt Safety",
            "prompt_entries": entries,
            "verdict": "PASS" if all_allowed else "FAIL",
        }

    async def generate_output_safety_report(self) -> dict[str, Any]:
        """Verify that mocked provider outputs pass the output firewall."""
        samples = []
        for provider_name, task in (
            ("deepseek_v4_flash", ModelTask.MARKET_THESIS),
            ("minimax_m3", ModelTask.RISK_CRITIQUE),
        ):
            mock = MockProvider()
            text, _ = await mock.complete("safe prompt", task)
            decision = self.output_firewall.check(text)
            samples.append(
                {
                    "provider": provider_name,
                    "task": task.value,
                    "output_firewall_safe": decision.safe,
                    "blocked_patterns": decision.blocked_patterns,
                }
            )
        all_safe = all(s["output_firewall_safe"] for s in samples)
        return {
            "generated_at": _now_iso(),
            "workstream": "V8.1: Live Model Output Safety",
            "samples": samples,
            "verdict": "PASS" if all_safe else "FAIL",
        }

    async def write_reports_v2(
        self,
        smoke_report: dict[str, Any] | None = None,
        safety_report: dict[str, Any] | None = None,
        output_report: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """Write V8.1 smoke, prompt-safety, and output-safety reports."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        smoke = smoke_report or {"generated_at": _now_iso(), "workstream": "V8.1: Live Model Smoke"}
        smoke_path = self.artifacts_dir / "live_model_smoke_report_v2.json"
        smoke_path.write_text(json.dumps(smoke, indent=2, default=str))
        paths["live_model_smoke_report_v2.json"] = smoke_path

        safety = safety_report or self.generate_prompt_safety_report_v2()
        safety_path = self.artifacts_dir / "live_model_prompt_safety_report_v2.json"
        safety_path.write_text(json.dumps(safety, indent=2, default=str))
        paths["live_model_prompt_safety_report_v2.json"] = safety_path

        output = output_report or await self.generate_output_safety_report()
        output_path = self.artifacts_dir / "live_model_output_safety_report_v1.json"
        output_path.write_text(json.dumps(output, indent=2, default=str))
        paths["live_model_output_safety_report_v1.json"] = output_path

        return paths


async def generate_live_model_smoke_report_v2(*, allow_live: bool = False) -> dict[str, Any]:
    """Generate the V8.1 report; live contact requires explicit manual opt-in."""
    smoke = LiveModelSmokeV2(allow_live=allow_live)
    return await smoke.run()


def generate_live_model_prompt_safety_report_v2() -> dict[str, Any]:
    """Public helper for the V8.1 report generator."""
    smoke = LiveModelSmokeV2()
    return smoke.generate_prompt_safety_report_v2()


async def generate_live_model_output_safety_report_v1() -> dict[str, Any]:
    """Public helper for the V8.1 report generator."""
    smoke = LiveModelSmokeV2()
    return await smoke.generate_output_safety_report()
# -----------------------------------------------------------------------------
# V8.2: credential-source-aware, route-mode-aware live smoke V3
# -----------------------------------------------------------------------------

class LiveModelSmokeV3(LiveModelSmokeV2):
    """V8.2 smoke runner with deterministic credential discovery and route mode.

    Status semantics:
      - LIVE_PROVEN: route mode + credentials + model resolution + live call OK.
      - OPERATOR_MODEL_CONFIG_REQUIRED: route or model ID unresolved.
      - PROVIDER_AUTH_FAILED: credentials rejected.
      - MOCK_ONLY: credentials absent or route mode is mock_only.
      - PROVIDER_TIMEOUT: external call timed out.

    Route and model resolution are skipped unless ``allow_live=True`` was
    passed explicitly by a direct manual caller.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credential_resolver = ProviderCredentialSourceResolver()
        self.credential_readiness = ProviderCredentialReadinessV2(self.credential_resolver)
        self.route_resolver = ProviderRouteModeResolver(self.credential_resolver)

    def _provider_prompt_and_task(self, name: str) -> tuple[str, ModelTask, str]:
        if "deepseek" in name.lower():
            return self.deepseek_prompt, ModelTask.MARKET_THESIS, "harmless market summary prompt"
        return self.minimax_prompt, ModelTask.RISK_CRITIQUE, "harmless risk critique prompt"

    async def _run_provider_v3(
        self,
        name: str,
    ) -> dict[str, Any]:
        prompt, task, prompt_summary = self._provider_prompt_and_task(name)

        if not self.live_contact_authorized:
            mock = MockProvider()
            text, metadata = await mock.complete(prompt, task, max_tokens=256, temperature=0.2)
            return {
                "provider": name,
                "model": "mock",
                "task": task.value,
                "configured_model": None,
                "resolved_model": None,
                "route_mode": "preflight_only",
                "intended_key_env": None,
                "credential_source": "not_checked",
                "api_key_present": None,
                "base_url_class": "not_checked",
                "prompt_digest": _sha256_digest(prompt),
                "prompt_summary": prompt_summary,
                "prompt_firewall_ok": True,
                "output_firewall_ok": self._output_safe(text),
                "order_instruction_free": self._order_instruction_free(text),
                "secret_free": self._secret_free(text),
                "error_class": None,
                "error_detail": None,
                "latency_ms": metadata.get("latency_ms", 0.0),
                "attempts": metadata.get("attempts", 0),
                "response_schema_ok": self._response_schema_ok(text, task),
                "status": "MOCK_ONLY",
                "contact_mode": "PREFLIGHT_ONLY",
            }

        configured = self.resolver._configured_model(name)
        candidate = self.resolver._endpoint_candidate(
            name, _DEFAULT_BASE_URLS.get(name, "")
        )
        route_result = self.route_resolver.resolve(
            name, candidate.api_base, configured
        )

        credential_resolution = self.credential_resolver.resolve(
            route_result.intended_key_env or candidate.api_key_env
        )

        base_result: dict[str, Any] = {
            "provider": name,
            "model": configured,
            "task": task.value,
            "configured_model": configured,
            "resolved_model": None,
            "route_mode": route_result.route_mode.value,
            "intended_key_env": route_result.intended_key_env,
            "credential_source": credential_resolution.source.value,
            "api_key_present": credential_resolution.present,
            "base_url_class": route_result.base_url_class,
            "prompt_digest": _sha256_digest(prompt),
            "prompt_summary": prompt_summary,
            "prompt_firewall_ok": True,
            "output_firewall_ok": True,
            "order_instruction_free": True,
            "secret_free": True,
            "error_class": None,
            "error_detail": None,
            "latency_ms": 0.0,
            "attempts": 0,
        }

        # MOCK_ONLY gate
        if (
            route_result.route_mode == ProviderRouteMode.MOCK_ONLY
            or not credential_resolution.present
        ):
            mock = MockProvider()
            text, metadata = await mock.complete(prompt, task, max_tokens=256, temperature=0.2)
            base_result.update(
                {
                    "model": "mock",
                    "status": "MOCK_ONLY",
                    "latency_ms": metadata.get("latency_ms", 0.0),
                    "attempts": metadata.get("attempts", 0),
                    "response_schema_ok": self._response_schema_ok(text, task),
                    "output_firewall_ok": self._output_safe(text),
                    "order_instruction_free": self._order_instruction_free(text),
                    "secret_free": self._secret_free(text),
                }
            )
            return base_result

        # Resolve model with bounded timeout.
        try:
            network_capability = issue_model_network_capability(
                allow_live=self.live_contact_authorized,
                source="legacy_live_model_smoke_v3_resolver",
            )
            resolution = await asyncio.wait_for(
                self.resolver.resolve(
                    name,
                    default_base=_DEFAULT_BASE_URLS.get(name),
                    default_aliases=_DEFAULT_ALIASES.get(name, []),
                    smoke_prompt=prompt,
                    allow_live=True,
                    network_capability=network_capability,
                ),
                timeout=SMOKE_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            resolution = ProviderResolutionResult(
                provider_name=name,
                status="PROVIDER_TIMEOUT",
                api_base=candidate.api_base,
                api_key_env=candidate.api_key_env,
                configured_model=configured,
                error_category="PROVIDER_TIMEOUT",
                error_detail="model resolution exceeded smoke call timeout",
            )

        base_result["resolved_model"] = resolution.resolved_model
        base_result["credential_source"] = (
            resolution.redacted_metadata.get("credential_source")
            or credential_resolution.source.value
        )
        base_result["route_mode"] = (
            resolution.redacted_metadata.get("route_mode")
            or route_result.route_mode.value
        )

        if resolution.status != "LIVE_PROVEN":
            base_result.update(
                {
                    "status": resolution.status,
                    "response_schema_ok": False,
                    "error_class": resolution.error_category,
                    "error_detail": resolution.error_detail,
                }
            )
            return base_result

        # Live smoke call.
        provider = self._build_resolved_provider(
            name,
            resolution.resolved_model or configured,
            resolution.api_base,
            api_key_env=resolution.api_key_env,
        )
        result = await self._execute_call(
            provider,
            prompt,
            task,
            prompt_summary,
            output_firewall_check=self._output_safe,
        )

        # Only claim LIVE_PROVEN when the live call itself succeeded.
        if result.status == "ok" and result.error_class is None:
            live_status = "LIVE_PROVEN"
        else:
            live_status = result.error_class or result.status or "PROVIDER_ERROR"

        base_result.update(
            {
                "model": resolution.resolved_model or configured,
                "status": live_status,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "response_schema_ok": result.response_schema_ok,
                "prompt_firewall_ok": result.firewall_ok,
                "output_firewall_ok": result.output_firewall_ok,
                "order_instruction_free": result.order_instruction_free,
                "secret_free": result.secret_free,
                "error_class": result.error_class,
            }
        )
        return base_result

    async def run(self) -> dict[str, Any]:
        """Run V8.2 credential-source-aware smoke for DeepSeek and Minimax."""
        ds_result = await self._run_provider_v3("deepseek_v4_flash")
        mm_result = await self._run_provider_v3("minimax_m3")

        results = [ds_result, mm_result]
        statuses = {r["status"] for r in results}

        if statuses == {"LIVE_PROVEN"}:
            live_model_status = "LIVE_PROVEN"
        elif "PROVIDER_AUTH_FAILED" in statuses:
            live_model_status = "PROVIDER_AUTH_FAILED"
        elif "OPERATOR_MODEL_CONFIG_REQUIRED" in statuses or "PROVIDER_TIMEOUT" in statuses:
            live_model_status = "OPERATOR_MODEL_CONFIG_REQUIRED"
        elif statuses == {"MOCK_ONLY"}:
            live_model_status = "MOCK_ONLY"
        else:
            live_model_status = "OPERATOR_MODEL_CONFIG_REQUIRED"

        all_safe = all(
            r["prompt_firewall_ok"] and r["output_firewall_ok"] and r["secret_free"]
            for r in results
        )

        return {
            "generated_at": _now_iso(),
            "workstream": "V8.2: Live Model Smoke",
            "live_model_status": live_model_status,
            "model_mode": live_model_status,
            "call_results": results,
            "verdict": "PASS" if all_safe else "FAIL",
            "live_contact_authorized": self.live_contact_authorized,
            "contact_mode": "LIVE_MANUAL" if self.live_contact_authorized else "PREFLIGHT_ONLY",
        }

    def generate_prompt_safety_report_v3(self) -> dict[str, Any]:
        """V8.2 prompt safety report with credential-source context."""
        prompts = [
            ("deepseek_v4_flash", self.deepseek_prompt, ModelTask.MARKET_THESIS.value),
            ("minimax_m3", self.minimax_prompt, ModelTask.RISK_CRITIQUE.value),
        ]
        entries = []
        all_allowed = True
        for provider_name, prompt, task in prompts:
            sanitized = self.firewall.sanitize(prompt)
            decision = self.firewall.block_check(sanitized)
            if not decision.allowed:
                all_allowed = False
            entries.append(
                {
                    "provider": provider_name,
                    "task": task,
                    "prompt_digest": _sha256_digest(prompt),
                    "prompt_summary": (
                        "harmless market summary prompt"
                        if provider_name == "deepseek_v4_flash"
                        else "harmless risk critique prompt"
                    ),
                    "firewall_classification": decision.classification,
                    "allowed": decision.allowed,
                    "matched_tokens": decision.matched_tokens,
                }
            )
        return {
            "generated_at": _now_iso(),
            "workstream": "V8.2: Live Model Prompt Safety",
            "prompt_entries": entries,
            "verdict": "PASS" if all_allowed else "FAIL",
        }

    async def generate_output_safety_report_v2(self) -> dict[str, Any]:
        """V8.2 output firewall report."""
        samples = []
        for provider_name, task in (
            ("deepseek_v4_flash", ModelTask.MARKET_THESIS),
            ("minimax_m3", ModelTask.RISK_CRITIQUE),
        ):
            mock = MockProvider()
            text, _ = await mock.complete("safe prompt", task)
            decision = self.output_firewall.check(text)
            samples.append(
                {
                    "provider": provider_name,
                    "task": task.value,
                    "output_firewall_safe": decision.safe,
                    "blocked_patterns": decision.blocked_patterns,
                }
            )
        all_safe = all(s["output_firewall_safe"] for s in samples)
        return {
            "generated_at": _now_iso(),
            "workstream": "V8.2: Live Model Output Safety",
            "samples": samples,
            "verdict": "PASS" if all_safe else "FAIL",
        }

    async def write_reports_v3(
        self,
        smoke_report: dict[str, Any] | None = None,
        safety_report: dict[str, Any] | None = None,
        output_report: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """Write V8.2 smoke, prompt-safety, and output-safety reports."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        smoke = smoke_report or {"generated_at": _now_iso(), "workstream": "V8.2: Live Model Smoke"}
        smoke_path = self.artifacts_dir / "live_model_smoke_report_v3.json"
        smoke_path.write_text(json.dumps(smoke, indent=2, default=str))
        paths["live_model_smoke_report_v3.json"] = smoke_path

        safety = safety_report or self.generate_prompt_safety_report_v3()
        safety_path = self.artifacts_dir / "live_model_prompt_safety_report_v3.json"
        safety_path.write_text(json.dumps(safety, indent=2, default=str))
        paths["live_model_prompt_safety_report_v3.json"] = safety_path

        output = output_report or await self.generate_output_safety_report_v2()
        output_path = self.artifacts_dir / "live_model_output_safety_report_v2.json"
        output_path.write_text(json.dumps(output, indent=2, default=str))
        paths["live_model_output_safety_report_v2.json"] = output_path

        return paths


async def generate_live_model_smoke_report_v3(*, allow_live: bool = False) -> dict[str, Any]:
    """Generate the V8.2 report; live contact requires explicit manual opt-in."""
    smoke = LiveModelSmokeV3(allow_live=allow_live)
    return await smoke.run()


def generate_live_model_prompt_safety_report_v3() -> dict[str, Any]:
    """Public helper for the V8.2 report generator."""
    smoke = LiveModelSmokeV3()
    return smoke.generate_prompt_safety_report_v3()


async def generate_live_model_output_safety_report_v2() -> dict[str, Any]:
    """Public helper for the V8.2 report generator."""
    smoke = LiveModelSmokeV3()
    return await smoke.generate_output_safety_report_v2()
