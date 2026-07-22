"""Read-only, secret-free status for Dummy's exact OpenRouter model panel.

The builder reads only local configuration, redacted credential presence, and
the bounded stored smoke artifact.  It imports no provider client and exposes
no action that can contact OpenRouter, mutate model settings, or confer
forecast/evidence/order authority.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model_router.credential_source import ProviderCredentialSourceResolver


MODEL_ARSENAL_SPECS: tuple[dict[str, str], ...] = (
    {
        "provider_alias": "gemini_3_6_flash",
        "display_name": "Gemini 3.6 Flash",
        "model": "google/gemini-3.6-flash",
        "task": "forecast_opinion",
        "role": "Rapid evidence extraction and independent probability forecast",
    },
    {
        "provider_alias": "gpt_5_6_luna",
        "display_name": "GPT-5.6 Luna",
        "model": "openai/gpt-5.6-luna",
        "task": "rapid_forecast",
        "role": "Low-latency structured forecast and research-only trade draft",
    },
    {
        "provider_alias": "claude_sonnet_5",
        "display_name": "Claude Sonnet 5",
        "model": "anthropic/claude-sonnet-5",
        "task": "strategy_critique",
        "role": "Deep market thesis, strategy critique, and synthesis review",
    },
    {
        "provider_alias": "glm_5_2",
        "display_name": "GLM-5.2",
        "model": "z-ai/glm-5.2",
        "task": "risk_critique",
        "role": "Independent risk, calibration, no-trade, and hypothesis critic",
    },
)

MODEL_ROUTING_RELATIVE_PATH = Path("configs/model_routing.json")
MODEL_SMOKE_RELATIVE_PATH = Path(
    "artifacts/dummy/openrouter_four_model_smoke_v1.json"
)
MAX_SMOKE_AGE_SECONDS = 24 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _artifact_age_seconds(value: Any, *, now: datetime) -> float | None:
    try:
        generated = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        return (now - generated.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return None


def build_model_arsenal_status(
    root: Path | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return current local panel status without provider contact or writes."""
    project_root = root or Path(__file__).resolve().parents[1]
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    routing = _read_json(project_root / MODEL_ROUTING_RELATIVE_PATH)
    provider_configs = routing.get("provider_configs") if routing else None
    provider_configs = provider_configs if isinstance(provider_configs, dict) else {}
    configured_hybrid = routing.get("hybrid_providers") if routing else None
    expected_aliases = tuple(spec["provider_alias"] for spec in MODEL_ARSENAL_SPECS)
    expected_pairs = {
        spec["provider_alias"]: (spec["model"], spec["task"])
        for spec in MODEL_ARSENAL_SPECS
    }
    configuration_exact = bool(
        isinstance(configured_hybrid, list)
        and tuple(configured_hybrid) == expected_aliases
        and all(
            isinstance(provider_configs.get(alias), dict)
            and provider_configs[alias].get("model_name") == model
            and provider_configs[alias].get("route_mode") == "openrouter"
            and provider_configs[alias].get("api_key_env") == "OPENROUTER_API_KEY"
            for alias, (model, _task) in expected_pairs.items()
        )
    )

    configured_value = routing.get("live_model_calls_enabled") if routing else None
    configured_gate = configured_value if type(configured_value) is bool else None
    runtime_value = os.environ.get("DUMMY_DEBATE_LIVE")
    runtime_opt_in = runtime_value == "1"
    runtime_state = (
        "ABSENT"
        if runtime_value is None
        else "ENABLED"
        if runtime_value == "1"
        else "DISABLED"
        if runtime_value == "0"
        else "INVALID"
    )
    two_key_gate_open = bool(configured_gate is True and runtime_opt_in)

    access = ProviderCredentialSourceResolver(project_root=project_root).resolve(
        "OPENROUTER_API_KEY"
    )
    background_panel_ready = bool(
        two_key_gate_open and configuration_exact and access.present
    )

    smoke = _read_json(project_root / MODEL_SMOKE_RELATIVE_PATH)
    calls = smoke.get("call_results") if smoke else None
    stored_expected = smoke.get("expected_panel") if smoke else None
    expected_panel_pairs = {
        (spec["provider_alias"], spec["model"])
        for spec in MODEL_ARSENAL_SPECS
    }
    stored_panel_pairs = {
        (row.get("provider_alias"), row.get("model"))
        for row in stored_expected
        if isinstance(row, dict)
    } if isinstance(stored_expected, list) else set()

    top_schema_valid = bool(
        smoke
        and type(smoke.get("schema_version")) is int
        and smoke.get("schema_version") == 1
        and smoke.get("mode") == "live"
        and isinstance(smoke.get("generated_at"), str)
        and isinstance(calls, list)
        and len(calls) == len(MODEL_ARSENAL_SPECS)
        and isinstance(stored_expected, list)
        and len(stored_expected) == len(MODEL_ARSENAL_SPECS)
        and smoke.get("secret_free") is True
        and smoke.get("response_content_stored") is False
        and smoke.get("calls_attempted") == len(MODEL_ARSENAL_SPECS)
        and smoke.get("call_cap") == len(MODEL_ARSENAL_SPECS)
    )

    calls_by_alias: dict[str, dict[str, Any]] = {}
    duplicate_alias = False
    if isinstance(calls, list):
        for row in calls:
            if not isinstance(row, dict):
                continue
            alias = row.get("provider_alias")
            if not isinstance(alias, str) or alias in calls_by_alias:
                duplicate_alias = True
                continue
            calls_by_alias[alias] = row

    exact_smoke_panel = bool(
        top_schema_valid
        and not duplicate_alias
        and stored_panel_pairs == expected_panel_pairs
        and set(calls_by_alias) == set(expected_pairs)
        and all(
            calls_by_alias[alias].get("requested_model") == model
            and calls_by_alias[alias].get("response_model") == model
            and calls_by_alias[alias].get("task") == task
            for alias, (model, task) in expected_pairs.items()
        )
    )
    all_calls_proven = bool(
        exact_smoke_panel
        and smoke
        and smoke.get("status") == "LIVE_PROVEN"
        and smoke.get("all_models_live_proven") is True
        and all(
            row.get("status") == "LIVE_PROVEN"
            and type(row.get("attempts")) is int
            and row.get("attempts") == 1
            and row.get("http_status") == 200
            and row.get("model_identity_ok") is True
            and row.get("response_schema_ok") is True
            and row.get("response_content_stored") is False
            for row in calls_by_alias.values()
        )
    )

    generated_at = smoke.get("generated_at") if smoke else None
    raw_age = _artifact_age_seconds(generated_at, now=now_utc)
    fresh = bool(
        raw_age is not None
        and -MAX_FUTURE_SKEW_SECONDS <= raw_age <= MAX_SMOKE_AGE_SECONDS
    )
    proof_current = bool(all_calls_proven and fresh)
    blockers: list[str] = []
    if not top_schema_valid:
        blockers.append("Stored smoke artifact is missing or fails schema-v1 redaction checks.")
    if top_schema_valid and not exact_smoke_panel:
        blockers.append("Stored smoke does not match the exact four-model roster and roles.")
    if exact_smoke_panel and not all_calls_proven:
        blockers.append("At least one stored model identity, response schema, or HTTP result failed.")
    if not fresh:
        blockers.append("Stored smoke is missing, stale, or too far in the future.")

    models: list[dict[str, Any]] = []
    for spec in MODEL_ARSENAL_SPECS:
        alias = spec["provider_alias"]
        provider = provider_configs.get(alias)
        provider = provider if isinstance(provider, dict) else {}
        call = calls_by_alias.get(alias, {})
        models.append({
            **spec,
            "configured_model": provider.get("model_name"),
            "configuration_match": bool(
                provider.get("model_name") == spec["model"]
                and provider.get("route_mode") == "openrouter"
            ),
            "route_mode": provider.get("route_mode"),
            "reasoning_effort": provider.get("reasoning_effort"),
            "smoke": {
                "status": call.get("status", "UNKNOWN"),
                "latency_ms": call.get("latency_ms"),
                "http_status": call.get("http_status"),
                "identity_ok": (
                    call.get("model_identity_ok")
                    if type(call.get("model_identity_ok")) is bool
                    else None
                ),
                "schema_ok": (
                    call.get("response_schema_ok")
                    if type(call.get("response_schema_ok")) is bool
                    else None
                ),
            },
        })

    costs = [
        row["reported_cost_usd"]
        for row in calls_by_alias.values()
        if isinstance(row.get("reported_cost_usd"), (int, float))
        and not isinstance(row.get("reported_cost_usd"), bool)
        and row["reported_cost_usd"] >= 0
    ]
    return {
        "data_status": "stored_redacted_smoke_and_local_configuration_only",
        "source": {
            "routing": MODEL_ROUTING_RELATIVE_PATH.as_posix(),
            "smoke": MODEL_SMOKE_RELATIVE_PATH.as_posix(),
            "runtime_opt_in": "dashboard_process_environment",
        },
        "provider_contacted_by_dashboard": False,
        "mutation_authority": False,
        "network_action_available": False,
        "openrouter_access": {
            "present": access.present,
            "source": access.source.value,
            "redacted": True,
            "required_env_name": "OPENROUTER_API_KEY",
        },
        "panel_configuration": {
            "exact": configuration_exact,
            "configured_gate": configured_gate,
            "runtime_opt_in": runtime_opt_in,
            "runtime_opt_in_state": runtime_state,
            "runtime_opt_in_scope": "dashboard_process_only",
            "two_key_paid_call_gate_open": two_key_gate_open,
            "background_panel_ready": background_panel_ready,
            "gate_status": "OPEN" if two_key_gate_open else "LOCKED",
        },
        "live_smoke": {
            "status": smoke.get("status", "UNKNOWN") if smoke else "UNKNOWN",
            "verdict": (
                "LIVE_CONNECTIVITY_PROVEN_CURRENT"
                if proof_current
                else "BLOCKED_MISSING_STALE_OR_INVALID_SMOKE"
            ),
            "generated_at": generated_at,
            "age_seconds": max(0.0, raw_age) if raw_age is not None else None,
            "fresh": fresh,
            "schema_valid": top_schema_valid,
            "exact_panel": exact_smoke_panel,
            "all_models_live_proven": proof_current,
            "models_proven": sum(
                1
                for row in calls_by_alias.values()
                if row.get("status") == "LIVE_PROVEN"
                and row.get("model_identity_ok") is True
                and row.get("response_schema_ok") is True
            ),
            "calls_attempted": smoke.get("calls_attempted") if smoke else None,
            "call_cap": smoke.get("call_cap") if smoke else None,
            "total_reported_cost_usd": round(sum(costs), 9) if costs else None,
            "response_content_stored": (
                smoke.get("response_content_stored")
                if smoke and type(smoke.get("response_content_stored")) is bool
                else None
            ),
            "blockers": blockers,
        },
        "authorities": {
            "evidence": False,
            "probability": False,
            "order": False,
        },
        "models": models,
    }

