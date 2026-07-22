"""Manual, redacted connectivity smoke for Dummy's exact OpenRouter panel.

The runner is deliberately separate from forecasting and execution.  It makes
no network request unless ``live=True`` is supplied by an explicit operator
command, performs at most one request per configured panel member, never
stores response content, and only reports a model as proven when OpenRouter's
response identifies the exact requested model.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from model_router.config import CONFIG_PATH, ModelRoutingConfig, load_model_routing_config
from model_router.credential_source import ProviderCredentialSourceResolver
from model_router.network_capability import (
    ModelNetworkCapability,
    issue_model_network_capability,
    require_model_network_capability,
)


OPENROUTER_API_BASE = "https://openrouter.ai/api"
OPENROUTER_CHAT_ENDPOINT = f"{OPENROUTER_API_BASE}/v1/chat/completions"
OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"
EXACT_PANEL: tuple[tuple[str, str], ...] = (
    ("gemini_3_6_flash", "google/gemini-3.6-flash"),
    ("gpt_5_6_luna", "openai/gpt-5.6-luna"),
    ("claude_sonnet_5", "anthropic/claude-sonnet-5"),
    ("glm_5_2", "z-ai/glm-5.2"),
)
DEFAULT_ARTIFACT_PATH = (
    Path(__file__).resolve().parent.parent
    / "artifacts"
    / "dummy"
    / "openrouter_four_model_smoke_v1.json"
)

_SMOKE_CASES: dict[str, tuple[str, str]] = {
    "gemini_3_6_flash": (
        "forecast_opinion",
        "This is a harmless integration smoke test, not a real market decision. "
        "Return only a JSON object with dummy_probability set to 0.50, "
        "confidence_score set to 0.10, and a short non-empty reasoning string.",
    ),
    "gpt_5_6_luna": (
        "rapid_forecast",
        "This is a harmless integration smoke test, not a real market decision. "
        "Return only a JSON object with dummy_probability 0.50, confidence_score "
        "0.10, reasoning as a short string, action as hold, and entry_condition "
        "as smoke test only.",
    ),
    "claude_sonnet_5": (
        "strategy_critique",
        "This is a harmless integration smoke test, not a real market decision. "
        "Return only a JSON object with verdict as warn and a short non-empty "
        "reasoning string.",
    ),
    "glm_5_2": (
        "risk_critique",
        "This is a harmless integration smoke test, not a real market decision. "
        "Return only a JSON object with risk_level as low and a short non-empty "
        "reasoning string.",
    ),
}


def _prompt_digest(alias: str) -> str:
    return hashlib.sha256(_SMOKE_CASES[alias][1].encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_exact_config(config: ModelRoutingConfig) -> list[str]:
    """Return non-secret configuration errors for the exact four-model panel."""
    errors: list[str] = []
    expected_aliases = [alias for alias, _ in EXACT_PANEL]
    if config.hybrid_providers != expected_aliases:
        errors.append("hybrid_providers must be the exact ordered four-model panel")

    for alias, expected_model in EXACT_PANEL:
        provider = config.provider_configs.get(alias)
        if provider is None:
            errors.append(f"{alias}: provider configuration missing")
            continue
        if provider.model_name != expected_model:
            errors.append(f"{alias}: exact model identifier mismatch")
        if provider.api_base.rstrip("/") != OPENROUTER_API_BASE:
            errors.append(f"{alias}: OpenRouter API base mismatch")
        if provider.api_key_env != OPENROUTER_KEY_ENV:
            errors.append(f"{alias}: credential reference mismatch")
        if provider.route_mode != "openrouter":
            errors.append(f"{alias}: route_mode must be openrouter")
    return errors


def _blank_call_result(alias: str, model: str, status: str) -> dict[str, Any]:
    return {
        "provider_alias": alias,
        "requested_model": model,
        "task": _SMOKE_CASES[alias][0],
        "response_model": None,
        "status": status,
        "model_identity_ok": False,
        "response_schema_ok": False,
        "latency_ms": 0.0,
        "attempts": 0,
        "http_status": None,
        "prompt_digest": _prompt_digest(alias),
        "usage_total_tokens": None,
        "reported_cost_usd": None,
        "response_content_stored": False,
    }


def _http_failure_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "PROVIDER_AUTH_FAILED"
    if status_code == 404:
        return "MODEL_NOT_FOUND"
    if status_code == 429:
        return "RATE_LIMITED"
    if 500 <= status_code <= 599:
        return "PROVIDER_UNAVAILABLE"
    return "HTTP_ERROR"


def _parse_smoke_content(alias: str, content: Any) -> bool:
    if not isinstance(content, str):
        return False
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        decoded = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(decoded, dict):
        return False

    def probability(value: Any) -> bool:
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float, str))
            and _finite_probability(value)
        )

    reasoning_ok = isinstance(decoded.get("reasoning"), str) and bool(
        decoded["reasoning"].strip()
    )
    if alias == "gemini_3_6_flash":
        return (
            probability(decoded.get("dummy_probability"))
            and probability(decoded.get("confidence_score"))
            and reasoning_ok
        )
    if alias == "gpt_5_6_luna":
        return (
            probability(decoded.get("dummy_probability"))
            and probability(decoded.get("confidence_score"))
            and reasoning_ok
            and str(decoded.get("action", "")).lower() == "hold"
            and isinstance(decoded.get("entry_condition"), str)
            and bool(decoded["entry_condition"].strip())
        )
    if alias == "claude_sonnet_5":
        return (
            str(decoded.get("verdict", "")).lower()
            in {"proceed", "warn", "block"}
            and reasoning_ok
        )
    if alias == "glm_5_2":
        return (
            str(decoded.get("risk_level", "")).lower()
            in {"low", "medium", "high", "critical"}
            and reasoning_ok
        )
    return False


def _finite_probability(value: Any) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed) and 0.0 <= parsed <= 1.0


def _safe_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or value < 0:
        return None
    return value


async def _smoke_one(
    client: httpx.AsyncClient,
    *,
    alias: str,
    model: str,
    api_key: str,
    timeout_seconds: float,
    max_tokens: int,
    reasoning_effort: str,
    network_capability: ModelNetworkCapability,
) -> dict[str, Any]:
    require_model_network_capability(network_capability)
    result = _blank_call_result(alias, model, "UNKNOWN")
    result["attempts"] = 1
    started = time.monotonic()
    task, prompt = _SMOKE_CASES[alias]
    result["task"] = task
    result["reasoning_effort"] = reasoning_effort
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning": {"effort": reasoning_effort},
        "response_format": {"type": "json_object"},
        # Fail closed instead of silently trying a different upstream route.
        "provider": {"allow_fallbacks": False},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dummy.local",
        "X-Title": "Dummy OpenRouter Panel Smoke",
    }
    try:
        response = await asyncio.wait_for(
            client.post(
                OPENROUTER_CHAT_ENDPOINT,
                headers=headers,
                json=body,
            ),
            timeout=timeout_seconds,
        )
        result["http_status"] = response.status_code
        if response.status_code != 200:
            result["status"] = _http_failure_status(response.status_code)
            return result

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            result["status"] = "RESPONSE_SCHEMA_INVALID"
            return result
        if not isinstance(payload, dict):
            result["status"] = "RESPONSE_SCHEMA_INVALID"
            return result

        response_model = payload.get("model")
        if isinstance(response_model, str):
            result["response_model"] = response_model
        result["model_identity_ok"] = response_model == model

        choices = payload.get("choices")
        content: Any = None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content")
        result["response_schema_ok"] = _parse_smoke_content(alias, content)

        usage = payload.get("usage")
        if isinstance(usage, dict):
            result["usage_total_tokens"] = _safe_number(usage.get("total_tokens"))
            result["reported_cost_usd"] = _safe_number(usage.get("cost"))

        if not result["model_identity_ok"]:
            result["status"] = "MODEL_IDENTITY_MISMATCH"
        elif not result["response_schema_ok"]:
            result["status"] = "RESPONSE_SCHEMA_INVALID"
        else:
            result["status"] = "LIVE_PROVEN"
        return result
    except (asyncio.TimeoutError, httpx.TimeoutException):
        result["status"] = "PROVIDER_TIMEOUT"
        return result
    except httpx.ConnectError:
        result["status"] = "CONNECT_ERROR"
        return result
    except httpx.HTTPError:
        result["status"] = "NETWORK_ERROR"
        return result
    finally:
        result["latency_ms"] = round((time.monotonic() - started) * 1000, 3)


async def run_openrouter_panel_smoke(
    *,
    live: bool = False,
    config_path: Path | None = None,
    project_root: Path | None = None,
    timeout_seconds: float = 20.0,
    max_tokens: int = 512,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Run a preflight or one-shot live smoke and return redacted evidence.

    ``live=False`` is the default and never retrieves the key value or creates
    an HTTP client.  Live mode is capped at one attempt for each of the four
    exact models.  A shared authentication failure stops further requests.
    """
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("timeout_seconds must be between 1 and 30")
    if not 64 <= max_tokens <= 512:
        raise ValueError("max_tokens must be between 64 and 512")

    live_authorized = live is True
    config = load_model_routing_config(config_path or CONFIG_PATH)
    resolver = ProviderCredentialSourceResolver(project_root=project_root)
    credential = resolver.resolve(OPENROUTER_KEY_ENV)
    config_errors = _validate_exact_config(config)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "workstream": "Exact four-model OpenRouter connectivity smoke",
        "mode": "live" if live_authorized else "preflight",
        "network_calls_authorized": live_authorized,
        "endpoint": OPENROUTER_API_BASE,
        "credential": credential.as_dict(),
        "configured_live_model_calls_enabled": config.live_model_calls_enabled,
        "expected_panel": [
            {"provider_alias": alias, "model": model} for alias, model in EXACT_PANEL
        ],
        "config_valid": not config_errors,
        "config_errors": config_errors,
        "call_cap": len(EXACT_PANEL),
        "calls_attempted": 0,
        "call_results": [],
        "all_models_live_proven": False,
        "response_content_stored": False,
        "secret_free": True,
    }

    if config_errors:
        report["status"] = "CONFIG_INVALID"
        return report
    if not credential.present:
        report["status"] = "CREDENTIAL_MISSING"
        return report
    if not live_authorized:
        report["status"] = "PREFLIGHT_READY"
        return report

    api_key = resolver.get_value(OPENROUTER_KEY_ENV)
    if not api_key:
        report["status"] = "CREDENTIAL_MISSING"
        return report

    network_capability = issue_model_network_capability(
        allow_live=True,
        source="manual_openrouter_panel_smoke",
    )

    timeout = httpx.Timeout(timeout_seconds)
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
        transport=transport,
    ) as client:
        shared_auth_failed = False
        for alias, model in EXACT_PANEL:
            if shared_auth_failed:
                report["call_results"].append(
                    _blank_call_result(alias, model, "SKIPPED_SHARED_AUTH_FAILURE")
                )
                continue
            call_result = await _smoke_one(
                client,
                alias=alias,
                model=model,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                reasoning_effort=(
                    config.provider_configs[alias].reasoning_effort or "low"
                ),
                network_capability=network_capability,
            )
            report["call_results"].append(call_result)
            report["calls_attempted"] += call_result["attempts"]
            shared_auth_failed = call_result["status"] == "PROVIDER_AUTH_FAILED"

    report["all_models_live_proven"] = all(
        row["status"] == "LIVE_PROVEN" for row in report["call_results"]
    ) and len(report["call_results"]) == len(EXACT_PANEL)
    report["status"] = (
        "LIVE_PROVEN" if report["all_models_live_proven"] else "LIVE_SMOKE_FAILED"
    )
    return report


def write_redacted_smoke_report(
    report: dict[str, Any],
    path: Path = DEFAULT_ARTIFACT_PATH,
) -> Path:
    """Atomically write a report that contains no prompts, keys, or content."""
    if report.get("response_content_stored") is not False or report.get("secret_free") is not True:
        raise ValueError("refusing to persist a non-redacted smoke report")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
