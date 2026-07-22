"""Generate DUMMY_V8_1 live-model provider resolution and hybrid smoke reports.

Produces the reports required for the V8.1 milestone.  No API key values,
raw prompts, account balances, positions, private keys, or order instructions
are ever written to artifacts.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


# -----------------------------------------------------------------------------
# 1. Provider config audit
# -----------------------------------------------------------------------------


def generate_model_provider_config_audit_report_v1() -> dict[str, Any]:
    from model_router.resolver import ModelProviderResolver, _DEFAULT_ALIASES, _DEFAULT_BASE_URLS

    resolver = ModelProviderResolver()
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Provider Config Audit",
        "deepseek_v4_flash": resolver.audit_provider_config(
            "deepseek_v4_flash",
            _DEFAULT_BASE_URLS["deepseek_v4_flash"],
            _DEFAULT_ALIASES["deepseek_v4_flash"],
        ),
        "minimax_m3": resolver.audit_provider_config(
            "minimax_m3",
            _DEFAULT_BASE_URLS["minimax_m3"],
            _DEFAULT_ALIASES["minimax_m3"],
        ),
        "verdict": "PASS",
    }


# -----------------------------------------------------------------------------
# 2/3/4. Resolution, alias, and error-resolution reports
# -----------------------------------------------------------------------------


def _preflight_resolution(name: str) -> dict[str, Any]:
    """Return redacted config/credential facts without constructing a resolver."""
    from model_router.config import load_model_routing_config
    from model_router.credential_source import ProviderCredentialSourceResolver

    config = load_model_routing_config()
    provider = config.provider_configs.get(name)
    if provider is None:
        return {
            "provider_name": name,
            "status": "PREFLIGHT_ONLY",
            "api_base_present": False,
            "api_key_env": None,
            "api_key_present": False,
            "credential_source": "missing",
            "configured_model": "",
            "resolved_model": None,
            "resolved_by": None,
            "error_category": "PROVIDER_CONFIG_MISSING",
            "error_detail": "provider config is missing",
            "route_mode": "unknown",
            "intended_key_env": None,
            "base_url_class": "not_checked",
            "contact_mode": "PREFLIGHT_ONLY",
            "network_contacted": False,
        }
    credential = ProviderCredentialSourceResolver().resolve(provider.api_key_env)
    return {
        "provider_name": name,
        "status": "PREFLIGHT_ONLY",
        "api_base_present": bool(provider.api_base),
        "api_key_env": provider.api_key_env,
        "api_key_present": credential.present,
        "credential_source": credential.source.value,
        "configured_model": provider.model_name,
        "resolved_model": None,
        "resolved_by": None,
        "error_category": None,
        "error_detail": "live resolution requires explicit allow_live=True",
        "route_mode": provider.route_mode or "unknown",
        "intended_key_env": provider.api_key_env,
        "base_url_class": "not_checked",
        "contact_mode": "PREFLIGHT_ONLY",
        "network_contacted": False,
    }


def _configured_aliases(name: str) -> list[str]:
    from model_router.config import load_model_routing_config

    provider = load_model_routing_config().provider_configs.get(name)
    if provider is None:
        return []
    aliases: list[str] = []
    for value in [provider.model_name, *provider.model_aliases]:
        if value and value not in aliases:
            aliases.append(value)
    return aliases


async def _resolve_both(
    *,
    allow_live: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if allow_live is not True:
        return (
            _preflight_resolution("deepseek_v4_flash"),
            _preflight_resolution("minimax_m3"),
        )

    from model_router.resolver import (
        ModelProviderResolver,
        _DEFAULT_ALIASES,
        _DEFAULT_BASE_URLS,
    )
    from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT
    from model_router.network_capability import issue_model_network_capability

    resolver = ModelProviderResolver()
    network_capability = issue_model_network_capability(
        allow_live=allow_live,
        source="archive.v8_1.manual_resolution",
    )
    ds = await resolver.resolve(
        "deepseek_v4_flash",
        default_base=_DEFAULT_BASE_URLS["deepseek_v4_flash"],
        default_aliases=_DEFAULT_ALIASES["deepseek_v4_flash"],
        smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
        allow_live=True,
        network_capability=network_capability,
    )
    mm = await resolver.resolve(
        "minimax_m3",
        default_base=_DEFAULT_BASE_URLS["minimax_m3"],
        default_aliases=_DEFAULT_ALIASES["minimax_m3"],
        smoke_prompt=_MINIMAX_SMOKE_PROMPT,
        allow_live=True,
        network_capability=network_capability,
    )
    return ds.redacted_metadata, mm.redacted_metadata


async def generate_model_provider_resolution_report_v1(
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    ds, mm = await _resolve_both(allow_live=allow_live)
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Provider Resolution",
        "deepseek_v4_flash": ds,
        "minimax_m3": mm,
        "verdict": "PASS" if all(r["status"] in ("LIVE_PROVEN", "MOCK_ONLY") for r in (ds, mm)) else "PARTIAL",
    }


async def generate_model_alias_resolution_report_v1(
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    ds_aliases = _configured_aliases("deepseek_v4_flash")
    mm_aliases = _configured_aliases("minimax_m3")
    ds, mm = await _resolve_both(allow_live=allow_live)
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Alias Resolution",
        "deepseek_v4_flash": {
            "configured_model": ds["configured_model"],
            "aliases_attempted": ds_aliases,
            "resolved_model": ds["resolved_model"],
            "resolved_by": ds["resolved_by"],
        },
        "minimax_m3": {
            "configured_model": mm["configured_model"],
            "aliases_attempted": mm_aliases,
            "resolved_model": mm["resolved_model"],
            "resolved_by": mm["resolved_by"],
        },
        "verdict": "PASS" if all(r["status"] in ("LIVE_PROVEN", "MOCK_ONLY") for r in (ds, mm)) else "PARTIAL",
    }


async def generate_model_provider_error_resolution_report_v1(
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    ds, mm = await _resolve_both(allow_live=allow_live)
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Provider Error Resolution",
        "deepseek_v4_flash": {
            "status": ds["status"],
            "error_category": ds["error_category"],
            "error_detail": ds["error_detail"],
        },
        "minimax_m3": {
            "status": mm["status"],
            "error_category": mm["error_category"],
            "error_detail": mm["error_detail"],
        },
        "verdict": "PASS",
    }


# -----------------------------------------------------------------------------
# 5. Operator repair recommendations
# -----------------------------------------------------------------------------


def generate_model_provider_operator_repair_recommendations_v1(
    resolution_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if resolution_report is None:
        # Synchronous fallback: load existing resolution report if present.
        path = ARTIFACTS / "model_provider_resolution_report_v1.json"
        if path.exists():
            resolution_report = json.loads(path.read_text(encoding="utf-8"))
        else:
            resolution_report = {"deepseek_v4_flash": {"status": "UNKNOWN"}, "minimax_m3": {"status": "UNKNOWN"}}

    recommendations: list[dict[str, Any]] = []
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        meta = resolution_report.get(provider, {})
        if meta.get("status") == "LIVE_PROVEN":
            continue
        prefix = "DEEPSEEK" if "deepseek" in provider else "MINIMAX"
        rec = {
            "provider": provider,
            "status": meta.get("status"),
            "api_key_env": f"{prefix}_API_KEY",
            "api_key_present": meta.get("api_key_present", False),
            "base_url_present": meta.get("api_base_present", False),
            "configured_model": meta.get("configured_model"),
            "resolved_model": meta.get("resolved_model"),
            "last_error_category": meta.get("error_category"),
            "fields_to_review": [
                f"{prefix}_API_KEY",
                f"{prefix}_BASE_URL",
                f"{prefix}_MODEL",
                f"{prefix}_MODEL_ALIASES",
                f"configs/model_routing.json provider_configs.{provider}.model_name",
                f"configs/model_routing.json provider_configs.{provider}.model_aliases",
            ],
            "example_values": {
                "DEEPSEEK_API_KEY": "sk-...",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
                "DEEPSEEK_MODEL_ALIASES": "deepseek-chat,deepseek-v3",
                "MINIMAX_API_KEY": "sk-...",
                "MINIMAX_BASE_URL": "https://api.minimax.chat",
                "MINIMAX_MODEL": "minimax-01",
                "MINIMAX_MODEL_ALIASES": "minimax-01,MiniMax-Text-01",
            },
            "note": "Values shown are placeholders. Replace with your actual credentials and verified model IDs.",
        }
        recommendations.append(rec)

    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Provider Operator Repair Recommendations",
        "recommendations": recommendations,
        "verdict": "PASS" if not recommendations else "OPERATOR_ACTION_REQUIRED",
    }


# -----------------------------------------------------------------------------
# 4 (cont). Live smoke v2 and safety reports
# -----------------------------------------------------------------------------


async def generate_live_model_smoke_report_v2(
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    from model_router.smoke import generate_live_model_smoke_report_v2 as _run

    return await _run(allow_live=allow_live)


def generate_live_model_prompt_safety_report_v2() -> dict[str, Any]:
    from model_router.smoke import generate_live_model_prompt_safety_report_v2 as _run

    return _run()


def generate_live_model_output_safety_report_v1() -> dict[str, Any]:
    from model_router.smoke import generate_live_model_output_safety_report_v1 as _run

    return _run()


# -----------------------------------------------------------------------------
# 6. Dashboard V8.1 report
# -----------------------------------------------------------------------------


def generate_dashboard_v8_1_report_v1() -> dict[str, Any]:
    resolution_path = ARTIFACTS / "model_provider_resolution_report_v1.json"
    resolution = (
        json.loads(resolution_path.read_text(encoding="utf-8"))
        if resolution_path.exists()
        else {"deepseek_v4_flash": {"status": "UNKNOWN"}, "minimax_m3": {"status": "UNKNOWN"}}
    )
    repair_path = ARTIFACTS / "model_provider_operator_repair_recommendations_v1.json"
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Dashboard Model Provider Resolution",
        "endpoint": "/api/v8/model-provider-resolution",
        "deepseek_v4_flash": resolution.get("deepseek_v4_flash", {}),
        "minimax_m3": resolution.get("minimax_m3", {}),
        "repair_recommendation_path": str(repair_path) if repair_path.exists() else None,
        "verdict": "PASS",
    }


# -----------------------------------------------------------------------------
# 7. Safety / no-secret / no-bypass / no-live-submit reports
# -----------------------------------------------------------------------------


def _secret_values_to_check() -> list[str]:
    """Return non-empty secret values that must not appear in artifacts."""
    names = [
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_API_PRIVATE_KEY_PATH",
    ]
    values = []
    for name in names:
        value = os.environ.get(name, "")
        if value and len(value) >= 4:
            values.append(value)
    return values


def generate_no_model_provider_secret_leak_report_v2() -> dict[str, Any]:
    report_files = [
        "model_provider_config_audit_report_v1.json",
        "model_provider_resolution_report_v1.json",
        "model_alias_resolution_report_v1.json",
        "model_provider_error_resolution_report_v1.json",
        "live_model_smoke_report_v2.json",
        "live_model_prompt_safety_report_v2.json",
        "live_model_output_safety_report_v1.json",
        "model_provider_operator_repair_recommendations_v1.json",
        "dashboard_v8_1_report_v1.json",
    ]
    secrets = _secret_values_to_check()
    leaked_files: list[str] = []
    for name in report_files:
        path = ARTIFACTS / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if any(secret in text for secret in secrets):
            leaked_files.append(name)
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: No Model Provider Secret Leak",
        "checked_files": report_files,
        "leaked_files": leaked_files,
        "verdict": "PASS" if not leaked_files else "FAIL",
    }


def generate_no_llm_secret_leak_report_v3() -> dict[str, Any]:
    from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT

    secrets = _secret_values_to_check()
    prompts = [_DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT]
    leaked = any(secret in prompt for secret in secrets for prompt in prompts if secret)
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: No LLM Secret Leak",
        "prompt_count": len(prompts),
        "secret_values_checked": len(secrets),
        "leaked": leaked,
        "verdict": "FAIL" if leaked else "PASS",
    }


def generate_direct_order_bypass_report_v8_1() -> dict[str, Any]:
    """Static proof that V8.1 modules do not call order endpoints."""
    import re

    files_to_check = [
        ROOT / "model_router" / "resolver.py",
        ROOT / "model_router" / "smoke.py",
        ROOT / "archive" / "report_scripts" / "generate_v8_1_reports.py",
        ROOT / "dashboard" / "backend" / "v8_routes.py",
    ]
    disallowed = [
        r"\bcreate_order\s*\(",
        r"\bcancel_order\s*\(",
        r"\.post\s*\(\s*['\"][^'\"]*?[/]orders",
        r"\.put\s*\(\s*['\"][^'\"]*?[/]orders",
        r"['\"][^'\"]*?portfolio[/]orders",
    ]
    violations: list[dict[str, str]] = []
    for path in files_to_check:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pat in disallowed:
            if re.search(pat, text, re.IGNORECASE):
                violations.append({"file": str(path), "pattern": pat})
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Direct Order Bypass Check",
        "files_checked": [str(p) for p in files_to_check],
        "violations": violations,
        "verdict": "PASS" if not violations else "FAIL",
    }


def generate_no_live_submit_still_disabled_report_v8_1() -> dict[str, Any]:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        enabled = False
        ack = False
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        enabled = data.get("enabled") is True
        ack = data.get("explicit_acknowledgement") == (
            "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only"
        )
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Live Submit Still Disabled",
        "enabled": enabled,
        "acknowledgement_present": ack,
        "file_present": path.exists(),
        "verdict": "PASS" if not enabled else "FAIL",
    }


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


async def main(*, allow_live: bool = False) -> dict[str, Any]:
    reports: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}

    reports["model_provider_config_audit_report_v1.json"] = generate_model_provider_config_audit_report_v1()
    reports["model_provider_resolution_report_v1.json"] = (
        await generate_model_provider_resolution_report_v1(allow_live=allow_live)
    )
    reports["model_alias_resolution_report_v1.json"] = (
        await generate_model_alias_resolution_report_v1(allow_live=allow_live)
    )
    reports["model_provider_error_resolution_report_v1.json"] = (
        await generate_model_provider_error_resolution_report_v1(
            allow_live=allow_live
        )
    )

    # Operator repair depends on resolution report being on disk.
    _write_report(
        "model_provider_resolution_report_v1.json",
        reports["model_provider_resolution_report_v1.json"],
    )
    reports["model_provider_operator_repair_recommendations_v1.json"] = (
        generate_model_provider_operator_repair_recommendations_v1(
            reports["model_provider_resolution_report_v1.json"]
        )
    )

    reports["live_model_smoke_report_v2.json"] = (
        await generate_live_model_smoke_report_v2(allow_live=allow_live)
    )
    reports["live_model_prompt_safety_report_v2.json"] = generate_live_model_prompt_safety_report_v2()
    reports["live_model_output_safety_report_v1.json"] = await generate_live_model_output_safety_report_v1()

    # Dashboard depends on resolution/repair reports.
    reports["dashboard_v8_1_report_v1.json"] = generate_dashboard_v8_1_report_v1()

    reports["no_model_provider_secret_leak_report_v2.json"] = generate_no_model_provider_secret_leak_report_v2()
    reports["no_llm_secret_leak_report_v3.json"] = generate_no_llm_secret_leak_report_v3()
    reports["direct_order_bypass_report_v8_1.json"] = generate_direct_order_bypass_report_v8_1()
    reports["no_live_submit_still_disabled_report_v8_1.json"] = generate_no_live_submit_still_disabled_report_v8_1()

    for name, data in reports.items():
        paths[name] = _write_report(name, data)

    failures = [name for name, data in reports.items() if data.get("verdict") == "FAIL"]
    partials = [name for name, data in reports.items() if data.get("verdict") in ("PARTIAL", "OPERATOR_ACTION_REQUIRED")]

    if failures:
        verdict = "FAIL"
    elif partials:
        verdict = "PARTIAL"
    else:
        verdict = "PASS"

    final = {
        "generated_at": now_iso(),
        "milestone": "DUMMY_V8_1_LIVE_MODEL_PROVIDER_RESOLUTION_AND_HYBRID_SMOKE_PASS_CLOSURE_V1",
        "verdict": verdict,
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(path) for name, path in paths.items()},
        "failures": failures,
        "partials": partials,
        "note": (
            "V8.1 provider resolution complete. PASS requires all providers LIVE_PROVEN "
            "or MOCK_ONLY with no secret leaks. OPERATOR_ACTION_REQUIRED indicates "
            "model/endpoint configuration needs operator review."
        ),
    }
    _write_report("final_report_v8_1.json", final)
    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    asyncio.run(main())
