import asyncio
import hashlib
import hmac
import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode
from live_firewall.exposure_tracker import get_persistent_exposure_tracker
from repo_harvester.runner import run_harvester
from repo_harvester.strategy_catalog import (
    resolve_strategy_catalog_path,
    sanitize_strategy_extraction_report,
)
from strategies.registry import STRATEGIES
from core.logger import logger
from core.secret_guard import redact
from dashboard.backend.operator_auth import operator_auth_status, require_operator
from model_router.credential_source import ProviderCredentialSourceResolver
from autonomy.target_policy import (
    is_data_only_target,
    is_prediction_quarantined_target,
    target_policy_payload,
)

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_SURFACE_ENV = "DUMMY_DASHBOARD_ARCHIVE_SURFACE"
ARCHIVE_SURFACE_VALUES = frozenset({"offline-dev", "test-only"})
ACTIVE_HYBRID_PROVIDERS = (
    "gemini_3_6_flash",
    "gpt_5_6_luna",
    "claude_sonnet_5",
    "glm_5_2",
)
MODEL_PANEL_SPECS = (
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
OPENROUTER_PANEL_SMOKE_PATH = Path(
    "artifacts/dummy/openrouter_four_model_smoke_v1.json"
)
MAX_LIVE_MODEL_PROOF_AGE_SECONDS = 24 * 60 * 60
MAX_LIVE_MODEL_PROOF_FUTURE_SKEW_SECONDS = 5 * 60
MAX_STORED_FORECAST_AGE_SECONDS = 24 * 60 * 60

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)
# Only the local dev/preview UI origins may call cross-origin; the served UI
# is same-origin. 5173 is the Vite dev server; 4173 is `npm run preview`
# (launch_dummy_dashboard.bat serves the built UI that way).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _archive_surface_enabled() -> bool:
    """Return true only for the explicit, non-production archive surface."""
    return os.environ.get(ARCHIVE_SURFACE_ENV, "").strip().lower() in ARCHIVE_SURFACE_VALUES


def _mount_archive_routes(target_app: FastAPI) -> int:
    """Mount historical routers only on the explicit offline/dev surface.

    Importing the archive is intentionally lazy. A normal production import of
    this module therefore cannot import or execute any of the 302 historical
    router modules, some of which contain provider/proof/process machinery.
    """
    import importlib
    import pkgutil
    import archive.routes

    mounted = 0
    for module_info in sorted(pkgutil.iter_modules(archive.routes.__path__), key=lambda item: item.name):
        module = importlib.import_module(f"archive.routes.{module_info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            target_app.include_router(router)
            mounted += 1
    return mounted


app.state.dashboard_surface = "production"
app.state.archive_router_count = 0
if _archive_surface_enabled():
    app.state.dashboard_surface = "offline_archive"
    app.state.archive_router_count = _mount_archive_routes(app)

from dashboard.backend import operator_routes  # noqa: E402
from dashboard.backend import operator_control_routes  # noqa: E402
from dashboard.backend import read_only_routes  # noqa: E402
from dashboard.backend import vnext_routes  # noqa: E402
app.include_router(operator_routes.router)
app.include_router(operator_control_routes.router)
app.include_router(read_only_routes.router)
app.include_router(vnext_routes.router)

@app.get("/status")
async def status():
    exposure = get_persistent_exposure_tracker()
    positions = (
        [position.model_dump(mode="json") for position in exposure.positions.values()]
        if exposure.state_healthy
        else None
    )
    orders = list(exposure.open_orders) if exposure.state_healthy else None
    total_exposure_cents = exposure.total_exposure_cents() if exposure.state_healthy else None
    return {
        "mode": STATE.mode.value,
        "kill_switch_active": STATE.kill_switch.active,
        "emergency_stop_active": STATE.emergency_stop.active,
        "kalshi_connected": STATE.kalshi_connected,
        "balance_cents": STATE.balance_cents,
        "daily_loss_cents": STATE.daily_loss_cents,
        "total_exposure_cents": total_exposure_cents,
        "exposure_state_status": "ready" if exposure.state_healthy else "unavailable",
        "exposure_state_error": getattr(exposure, "persistence_error", None),
        "open_positions": positions,
        "open_orders": orders,
        "position_order_source": "runtime/live_exposure_state.json",
        "dashboard_surface": app.state.dashboard_surface,
    }


@app.get("/operator-auth/status")
async def dashboard_operator_auth_status(request: Request):
    """Secret-free setup probe used by the local operator UI."""
    return operator_auth_status(request)

@app.get("/api/v8/model-provider-resolution")
async def api_v8_model_provider_resolution():
    """Return configured routing only; a dashboard GET never calls a provider."""
    routing = _read_json_file(ROOT / "configs" / "model_routing.json")
    if not isinstance(routing, dict):
        raise HTTPException(status_code=503, detail="model routing configuration is missing or malformed")
    provider_configs = routing.get("provider_configs")
    if not isinstance(provider_configs, dict):
        raise HTTPException(status_code=503, detail="model routing provider configuration is malformed")
    providers: dict[str, dict] = {}
    for name in ACTIVE_HYBRID_PROVIDERS:
        config = provider_configs.get(name)
        if not isinstance(config, dict):
            providers[name] = {"status": "BLOCKED_MISSING_PROVIDER_CONFIG"}
            continue
        providers[name] = {
            "status": "CONFIGURED_NOT_PROBED_BY_DASHBOARD",
            "model_name": config.get("model_name"),
            "route_mode": config.get("route_mode"),
            "required_env_name": config.get("api_key_env"),
        }
    return redact({
        "providers": providers,
        "hybrid_providers": list(ACTIVE_HYBRID_PROVIDERS),
        "live_model_calls_enabled": routing.get("live_model_calls_enabled") is True,
        "data_status": "configuration_only_no_provider_contact",
        "provider_contacted": False,
        "source": "configs/model_routing.json",
    })

@app.get("/api/v8/provider-credential-source")
async def api_v8_provider_credential_source():
    credential_resolver = ProviderCredentialSourceResolver()
    routing = _read_json_file(ROOT / "configs" / "model_routing.json")
    provider_configs = routing.get("provider_configs") if isinstance(routing, dict) else None
    if not isinstance(provider_configs, dict):
        raise HTTPException(status_code=503, detail="model routing provider configuration is malformed")
    data: dict[str, dict] = {}
    for provider in ACTIVE_HYBRID_PROVIDERS:
        config = provider_configs.get(provider)
        if not isinstance(config, dict):
            data[provider] = {"status": "BLOCKED_MISSING_PROVIDER_CONFIG"}
            continue
        key_env = str(config.get("api_key_env") or "")
        credential = credential_resolver.resolve(key_env)
        data[provider] = {
            "required_env_name": key_env,
            "source": credential.source.value,
            "present": credential.present,
            "route_mode": config.get("route_mode"),
            "model_name": config.get("model_name"),
        }
    return redact({
        "providers": data,
        "provider_contacted": False,
        "data_status": "credential_presence_only",
    })

@app.get("/api/v8/provider-route-mode")
async def api_v8_provider_route_mode():
    routing = _read_json_file(ROOT / "configs" / "model_routing.json")
    provider_configs = routing.get("provider_configs") if isinstance(routing, dict) else None
    if not isinstance(provider_configs, dict):
        raise HTTPException(status_code=503, detail="model routing provider configuration is malformed")
    data = {
        provider: {
            "route_mode": provider_configs.get(provider, {}).get("route_mode"),
            "model_name": provider_configs.get(provider, {}).get("model_name"),
            "required_env_name": provider_configs.get(provider, {}).get("api_key_env"),
        }
        for provider in ACTIVE_HYBRID_PROVIDERS
    }
    return redact({"providers": data, "provider_contacted": False})

def _model_panel_status() -> dict:
    """Build the secret-free panel from local config and stored smoke evidence.

    This helper deliberately has no provider client and no network-capable
    dependency. Reading the dashboard can therefore never spend money or turn
    a connectivity smoke into forecast, evidence, or order authority.
    """
    routing = _read_json_file(ROOT / "configs" / "model_routing.json")
    provider_configs = routing.get("provider_configs") if isinstance(routing, dict) else None
    configured_hybrid = routing.get("hybrid_providers") if isinstance(routing, dict) else None
    provider_configs = provider_configs if isinstance(provider_configs, dict) else {}

    configured_gate_value = (
        routing.get("live_model_calls_enabled") if isinstance(routing, dict) else None
    )
    configured_gate = (
        configured_gate_value if type(configured_gate_value) is bool else None
    )
    runtime_opt_in_raw = os.environ.get("DUMMY_DEBATE_LIVE")
    runtime_opt_in = runtime_opt_in_raw == "1"
    if runtime_opt_in_raw is None:
        runtime_opt_in_state = "ABSENT"
    elif runtime_opt_in_raw == "1":
        runtime_opt_in_state = "ENABLED"
    elif runtime_opt_in_raw == "0":
        runtime_opt_in_state = "DISABLED"
    else:
        runtime_opt_in_state = "INVALID"

    expected_pairs = {
        spec["provider_alias"]: (spec["model"], spec["task"])
        for spec in MODEL_PANEL_SPECS
    }
    configuration_exact = bool(
        isinstance(configured_hybrid, list)
        and tuple(configured_hybrid) == ACTIVE_HYBRID_PROVIDERS
        and all(
            isinstance(provider_configs.get(alias), dict)
            and provider_configs[alias].get("model_name") == model
            and provider_configs[alias].get("route_mode") == "openrouter"
            and provider_configs[alias].get("api_key_env") == "OPENROUTER_API_KEY"
            for alias, (model, _task) in expected_pairs.items()
        )
    )

    access = ProviderCredentialSourceResolver(project_root=ROOT).resolve(
        "OPENROUTER_API_KEY"
    )
    two_key_gate_open = bool(configured_gate is True and runtime_opt_in)
    background_panel_ready = bool(
        two_key_gate_open and configuration_exact and access.present
    )

    smoke_path = ROOT / OPENROUTER_PANEL_SMOKE_PATH
    smoke = _read_json_file(smoke_path)
    calls = smoke.get("call_results") if isinstance(smoke, dict) else None
    expected_panel = smoke.get("expected_panel") if isinstance(smoke, dict) else None
    expected_panel_pairs = {
        (spec["provider_alias"], spec["model"])
        for spec in MODEL_PANEL_SPECS
    }
    stored_panel_pairs = {
        (row.get("provider_alias"), row.get("model"))
        for row in expected_panel
        if isinstance(row, dict)
    } if isinstance(expected_panel, list) else set()
    top_level_schema_valid = bool(
        isinstance(smoke, dict)
        and type(smoke.get("schema_version")) is int
        and smoke.get("schema_version") == 1
        and smoke.get("mode") == "live"
        and isinstance(smoke.get("generated_at"), str)
        and isinstance(calls, list)
        and len(calls) == len(MODEL_PANEL_SPECS)
        and isinstance(expected_panel, list)
        and len(expected_panel) == len(MODEL_PANEL_SPECS)
        and smoke.get("secret_free") is True
        and smoke.get("response_content_stored") is False
        and smoke.get("calls_attempted") == len(MODEL_PANEL_SPECS)
        and smoke.get("call_cap") == len(MODEL_PANEL_SPECS)
    )

    call_by_alias: dict[str, dict] = {}
    duplicate_alias = False
    if isinstance(calls, list):
        for row in calls:
            if not isinstance(row, dict):
                continue
            alias = row.get("provider_alias")
            if not isinstance(alias, str) or alias in call_by_alias:
                duplicate_alias = True
                continue
            call_by_alias[alias] = row

    exact_panel = bool(
        top_level_schema_valid
        and not duplicate_alias
        and stored_panel_pairs == expected_panel_pairs
        and set(call_by_alias) == set(expected_pairs)
        and all(
            call_by_alias[alias].get("requested_model") == model
            and call_by_alias[alias].get("response_model") == model
            and call_by_alias[alias].get("task") == task
            for alias, (model, task) in expected_pairs.items()
        )
    )
    all_calls_proven = bool(
        exact_panel
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
            for row in call_by_alias.values()
        )
    )

    generated_at = smoke.get("generated_at") if isinstance(smoke, dict) else None
    raw_age_seconds = None
    try:
        generated = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        raw_age_seconds = (
            datetime.now(timezone.utc) - generated.astimezone(timezone.utc)
        ).total_seconds()
    except (TypeError, ValueError, OverflowError):
        pass
    fresh = bool(
        raw_age_seconds is not None
        and -MAX_LIVE_MODEL_PROOF_FUTURE_SKEW_SECONDS
        <= raw_age_seconds
        <= MAX_LIVE_MODEL_PROOF_AGE_SECONDS
    )
    age_seconds = max(0.0, raw_age_seconds) if raw_age_seconds is not None else None
    connectivity_proof_current = bool(all_calls_proven and fresh)

    blockers: list[str] = []
    if not top_level_schema_valid:
        blockers.append("stored smoke artifact is missing or fails schema-v1 redaction checks")
    if top_level_schema_valid and not exact_panel:
        blockers.append("stored smoke does not cover exactly one call for each configured panel model and role")
    if exact_panel and not all_calls_proven:
        blockers.append("one or more stored model calls failed identity, schema, HTTP, or one-attempt checks")
    if not fresh:
        blockers.append("stored smoke timestamp is missing, too old, or too far in the future")

    model_rows = []
    for spec in MODEL_PANEL_SPECS:
        alias = spec["provider_alias"]
        provider_config = provider_configs.get(alias)
        provider_config = provider_config if isinstance(provider_config, dict) else {}
        call = call_by_alias.get(alias, {})
        model_rows.append({
            **spec,
            "configured_model": provider_config.get("model_name"),
            "configuration_match": bool(
                provider_config.get("model_name") == spec["model"]
                and provider_config.get("route_mode") == "openrouter"
            ),
            "route_mode": provider_config.get("route_mode"),
            "reasoning_effort": provider_config.get("reasoning_effort"),
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
                "reported_cost_usd": call.get("reported_cost_usd"),
            },
        })

    reported_costs = [
        row.get("reported_cost_usd")
        for row in call_by_alias.values()
        if isinstance(row.get("reported_cost_usd"), (int, float))
        and not isinstance(row.get("reported_cost_usd"), bool)
        and row["reported_cost_usd"] >= 0
    ]
    total_reported_cost = round(sum(reported_costs), 9) if reported_costs else None

    return redact({
        "data_status": "stored_redacted_smoke_and_local_configuration_only",
        "source": {
            "routing": "configs/model_routing.json",
            "smoke": OPENROUTER_PANEL_SMOKE_PATH.as_posix(),
            "runtime_opt_in": "dashboard_process_environment",
        },
        "provider_contacted_by_dashboard": False,
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
            "persistent_gate_source": "configs/model_routing.json",
            "runtime_opt_in": runtime_opt_in,
            "runtime_opt_in_state": runtime_opt_in_state,
            "runtime_opt_in_scope": "dashboard_process_only",
            "two_key_paid_call_gate_open": two_key_gate_open,
            "background_panel_ready": background_panel_ready,
            "gate_status": "OPEN" if two_key_gate_open else "LOCKED",
        },
        "live_smoke": {
            "status": smoke.get("status", "UNKNOWN") if isinstance(smoke, dict) else "UNKNOWN",
            "verdict": (
                "LIVE_CONNECTIVITY_PROVEN_CURRENT"
                if connectivity_proof_current
                else "BLOCKED_MISSING_STALE_OR_INVALID_SMOKE"
            ),
            "generated_at": generated_at,
            "age_seconds": age_seconds,
            "fresh": fresh,
            "schema_valid": top_level_schema_valid,
            "exact_panel": exact_panel,
            "all_models_live_proven": connectivity_proof_current,
            "calls_attempted": smoke.get("calls_attempted") if isinstance(smoke, dict) else None,
            "call_cap": smoke.get("call_cap") if isinstance(smoke, dict) else None,
            "models_proven": sum(
                1 for row in call_by_alias.values()
                if row.get("status") == "LIVE_PROVEN"
                and row.get("model_identity_ok") is True
                and row.get("response_schema_ok") is True
            ),
            "total_reported_cost_usd": total_reported_cost,
            "response_content_stored": (
                smoke.get("response_content_stored")
                if isinstance(smoke, dict)
                and type(smoke.get("response_content_stored")) is bool
                else None
            ),
            "blockers": blockers,
        },
        "authorities": {
            "evidence": False,
            "probability": False,
            "order": False,
        },
        "models": model_rows,
        # Compatibility fields for clients of the retired V8 proof shape.
        "proof_schema_valid": top_level_schema_valid,
        "proof_current_for_active_hybrid": connectivity_proof_current,
        "evidence_authority": False,
        "order_authority": False,
        "verdict": (
            "LIVE_CONNECTIVITY_PROVEN_CURRENT"
            if connectivity_proof_current
            else "BLOCKED_MISSING_STALE_OR_INVALID_SMOKE"
        ),
    })


@app.get("/api/read-only/model-panel")
async def api_read_only_model_panel():
    """Return local, redacted panel status; never contact a model provider."""
    return _model_panel_status()


@app.get("/api/v8/live-model-proof")
async def api_v8_live_model_proof():
    """Compatibility alias for the current exact-panel read-only contract."""
    return _model_panel_status()

def _read_json_file(path: Path):
    """Parse a JSON file; return None if missing or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _proof_bundle_summary(path: Path) -> tuple[dict | None, str | None]:
    """Validate one proof-ledger bundle against the writer's integrity rules."""
    bundle = _read_json_file(path)
    if not isinstance(bundle, dict):
        return None, "malformed_json_or_non_object"
    required = ("ref_id", "timestamp", "component", "verdict", "payload_hash", "payload")
    if any(key not in bundle for key in required):
        return None, "missing_required_fields"
    if str(bundle.get("ref_id")) != path.stem:
        return None, "ref_id_filename_mismatch"
    if not all(isinstance(bundle.get(key), str) and bool(bundle.get(key)) for key in required[:5]):
        return None, "invalid_identity_or_verdict_fields"
    if not isinstance(bundle.get("payload"), dict):
        return None, "payload_not_object"
    try:
        parsed = datetime.fromisoformat(str(bundle["timestamp"]).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None, "timestamp_not_timezone_aware"
    except (TypeError, ValueError, OverflowError):
        return None, "timestamp_invalid"
    expected_hash = hashlib.sha256(
        json.dumps(bundle["payload"], sort_keys=True, default=str).encode()
    ).hexdigest()
    if not isinstance(bundle["payload_hash"], str) or not hmac.compare_digest(
        bundle["payload_hash"].lower(), expected_hash.lower()
    ):
        return None, "payload_hash_mismatch"
    return {
        "ref_id": bundle["ref_id"],
        "timestamp": bundle["timestamp"],
        "component": bundle["component"],
        "verdict": bundle["verdict"],
        "payload_hash": bundle["payload_hash"],
        "integrity_valid": True,
    }, None


@app.get("/markets")
async def markets():
    caps = load_caps()
    allowlists = _read_json_file(ROOT / "configs" / "allowlists.json")
    return {
        "allowed_markets": caps.allowed_markets,
        "blocked_categories": caps.blocked_categories,
        # None (unknown) when the allowlist store is unreadable — never a
        # fabricated category list.
        "market_categories": allowlists.get("categories") if isinstance(allowlists, dict) else None,
        "source": "configs/caps.json + configs/allowlists.json",
        "data_status": "configuration_only",
        "live_market_snapshot_available": False,
    }


@app.get("/forecasts")
async def forecasts(limit: int = 500):
    """Stored forecast records; 501 when no store exists.

    These rows are returned as observations exactly as stored.  The endpoint
    deliberately does not call them live, calibrated, or settlement-backed.
    """
    path = ROOT / "data" / "calibration" / "forecasts.jsonl"
    if not path.exists():
        raise HTTPException(
            status_code=501,
            detail="no forecast store at data/calibration/forecasts.jsonl — "
                   "the calibration pipeline has not produced any forecasts",
        )
    bounded_limit = min(500, max(1, int(limit)))
    records: deque[dict] = deque(maxlen=bounded_limit)
    skipped = 0
    stored_record_count = 0
    eligible_count = 0
    data_only_excluded_count = 0
    non_prediction_excluded_count = 0
    probabilities: set[str] = set()
    freshness_counts = {
        "fresh_stored": 0,
        "stale_stored": 0,
        "timestamp_missing": 0,
        "timestamp_invalid": 0,
        "future_timestamp": 0,
    }
    target_policy_counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(record, dict):
                skipped += 1
                continue
            stored_record_count += 1
            ticker = str(
                record.get("contract_ticker")
                or record.get("market_ticker")
                or ""
            )
            category = record.get("category") or record.get("market_category")
            vertical = record.get("vertical")
            target_policy = target_policy_payload(
                ticker,
                category=category,
                vertical=vertical,
                series_tags=record.get("series_tags") or record.get("tags"),
            )
            classification = str(target_policy["classification"])
            target_policy_counts[classification] = (
                target_policy_counts.get(classification, 0) + 1
            )
            if is_data_only_target(
                ticker,
                category=category,
                vertical=vertical,
            ):
                data_only_excluded_count += 1
                non_prediction_excluded_count += 1
                continue
            if is_prediction_quarantined_target(
                ticker,
                category=category,
                vertical=vertical,
                series_tags=record.get("series_tags") or record.get("tags"),
            ):
                non_prediction_excluded_count += 1
                continue
            eligible_count += 1
            observation = {
                key: value
                for key, value in record.items()
                if key not in {"valuation_evidence", "valuation_evidence_status"}
            }
            timestamp_value = next(
                (
                    observation.get(key)
                    for key in ("timestamp", "observed_at", "generated_at", "created_at")
                    if observation.get(key) is not None
                ),
                None,
            )
            age_seconds = None
            if timestamp_value is None:
                freshness_status = "timestamp_missing"
            else:
                try:
                    observed_at = datetime.fromisoformat(
                        str(timestamp_value).replace("Z", "+00:00")
                    )
                    if observed_at.tzinfo is None:
                        raise ValueError("timestamp is not timezone-aware")
                    age_seconds = (now - observed_at.astimezone(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    freshness_status = "timestamp_invalid"
                    age_seconds = None
                else:
                    if age_seconds < -MAX_LIVE_MODEL_PROOF_FUTURE_SKEW_SECONDS:
                        freshness_status = "future_timestamp"
                    elif age_seconds > MAX_STORED_FORECAST_AGE_SECONDS:
                        freshness_status = "stale_stored"
                    else:
                        freshness_status = "fresh_stored"
            freshness_counts[freshness_status] += 1
            observation["observation_timestamp"] = timestamp_value
            observation["observation_age_seconds"] = (
                round(age_seconds, 3) if age_seconds is not None else None
            )
            observation["freshness_status"] = freshness_status
            observation["target_policy"] = target_policy
            observation["target_classification"] = classification
            observation["prediction_target"] = target_policy["prediction_target"]
            observation["trade_proposal_authority"] = target_policy[
                "trade_proposal_authority"
            ]
            observation["row_actionable"] = False
            observation["actionability_reason"] = "stored_unverified_observation_only"
            records.append(observation)
            if record.get("dummy_probability") is not None:
                probabilities.add(str(record["dummy_probability"]))
    quality_status = "stored_unverified"
    if eligible_count and len(probabilities) <= 1:
        quality_status = "insufficient_probability_variation"
    elif not eligible_count:
        quality_status = "no_eligible_prediction_targets"
    return {
        "forecasts": list(records),
        "count": eligible_count,
        "stored_record_count": stored_record_count,
        "data_only_forecasts_excluded": data_only_excluded_count,
        "non_prediction_targets_excluded": non_prediction_excluded_count,
        "target_policy_counts": target_policy_counts,
        "skipped_malformed": skipped,
        "source": "data/calibration/forecasts.jsonl",
        "data_status": quality_status,
        "freshness_counts": freshness_counts,
        "max_stored_forecast_age_seconds": MAX_STORED_FORECAST_AGE_SECONDS,
        "forecast_rows_are_actionable": False,
        "settlement_backed_performance_claim": False,
    }


@app.get("/strategies")
async def strategies():
    """Registered strategies plus repo-derived candidates from the extraction
    report (same source the StrategyCandidates screen uses).

    The read path always applies the current local sanitizer.  A stale v1
    artifact is therefore safe to inspect without rerunning the network-backed
    harvester and cannot restore authority through old metadata.
    """
    report_path = resolve_strategy_catalog_path(ROOT)
    report = _read_json_file(report_path)
    if not isinstance(report, dict):
        raise HTTPException(
            status_code=501,
            detail="strategy candidate report unavailable at "
                   f"{report_path}",
        )
    raw_candidates = report.get("candidates")
    if not isinstance(raw_candidates, list):
        eligible_candidates = None
        data_only_excluded: list[str] | None = None
        unknown_target_excluded = None
    else:
        governed = sanitize_strategy_extraction_report(report)
        eligible_candidates = governed["candidates"]
        data_only_excluded = [
            str(row.get("strategy_name") or "UNKNOWN")
            for row in governed["data_only_inputs"]
        ]
        unknown_target_excluded = governed["unknown_target_excluded_count"]

    return {
        "registered_strategies": [s.__class__.__name__ for s in STRATEGIES],
        "repo_derived_candidates": eligible_candidates,
        "candidate_count": len(eligible_candidates) if eligible_candidates is not None else None,
        "reported_candidate_count": report.get("candidate_count"),
        "data_only_candidates_excluded": (
            len(data_only_excluded) if data_only_excluded is not None else None
        ),
        "data_only_strategy_names": (
            sorted(set(data_only_excluded)) if data_only_excluded is not None else None
        ),
        "unknown_target_candidates_excluded": unknown_target_excluded,
        "catalog_grants_prediction_authority": False,
        "catalog_grants_execution_authority": False,
        "source": str(report_path.relative_to(ROOT)).replace("\\", "/"),
        "data_status": (
            "governed_stored_report_filtered_by_target_policy"
            if isinstance(raw_candidates, list)
            else "stored_report_incomplete"
        ),
    }

@app.get("/orders")
async def orders():
    exposure = get_persistent_exposure_tracker()
    if not exposure.state_healthy:
        raise HTTPException(
            status_code=503,
            detail=f"persistent order/exposure state is unavailable: {exposure.persistence_error}",
        )
    return {
        "orders": list(exposure.open_orders),
        "count": len(exposure.open_orders),
        "source": "runtime/live_exposure_state.json",
        "data_status": "persistent_broker_reconciled_state",
    }

@app.get("/positions")
async def positions():
    exposure = get_persistent_exposure_tracker()
    if not exposure.state_healthy:
        raise HTTPException(
            status_code=503,
            detail=f"persistent order/exposure state is unavailable: {exposure.persistence_error}",
        )
    rows = [position.model_dump(mode="json") for position in exposure.positions.values()]
    return {
        "positions": rows,
        "count": len(rows),
        "source": "runtime/live_exposure_state.json",
        "data_status": "persistent_broker_fill_witnessed_state",
    }

@app.get("/risk")
async def risk():
    return {
        "caps": load_caps().model_dump(),
        "daily_loss_cents": STATE.daily_loss_cents,
        "daily_loss_status": "stored_runtime_unverified",
        "source": "configs/caps.json + runtime_state",
        "data_status": "stored_configuration_and_runtime_telemetry",
        "live_broker_snapshot_available": False,
    }

@app.get("/proof")
async def proof(limit: int = 50):
    """Integrity-validated proof-ledger summary from the on-disk ledger."""
    proof_dir = ROOT / "proof"
    if not proof_dir.exists():
        raise HTTPException(
            status_code=501,
            detail="proof ledger directory proof/ is not present",
        )
    bounded_limit = min(500, max(1, int(limit)))
    files = sorted(proof_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    recent = []
    invalid: list[dict[str, str]] = []
    for path in files[:bounded_limit]:
        summary, error = _proof_bundle_summary(path)
        if summary is None:
            invalid.append({"file": path.name, "reason": error or "unknown_validation_error"})
        else:
            recent.append(summary)
    return {
        "proof_count": len(recent),
        "total_files": len(files),
        "proofs": recent,
        "invalid_count": len(invalid),
        "invalid": invalid,
        "source": "proof/",
        "data_status": "verified_integrity" if not invalid else "blocked_partial_integrity_failure",
        "proof_authority_granted": False,
    }

@app.get("/logs")
async def logs(limit: int = 100):
    log_file = ROOT / "logs" / "dummy.jsonl"
    if not log_file.exists():
        return {
            "logs": None,
            "skipped_malformed": None,
            "source": "logs/dummy.jsonl",
            "data_status": "unavailable",
            "unavailable_reason": "local_log_file_missing",
        }
    bounded_limit = min(1000, max(1, int(limit)))
    entries = []
    skipped = 0
    if log_file.exists():
        with log_file.open(encoding="utf-8") as f:
            lines = deque(f, maxlen=bounded_limit)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # Tolerate truncated/corrupt lines instead of 500ing.
                skipped += 1
    return {
        "logs": entries,
        "skipped_malformed": skipped,
        "source": "logs/dummy.jsonl",
        "data_status": "stored_observations",
    }

@app.get("/repo-harvester/status")
async def repo_harvester_status():
    return {
        "status": None,
        "source": "unavailable",
        "data_status": "unavailable",
        "unavailable_reason": "no_persistent_harvester_run_state",
    }

@app.get("/repo-harvester/repos")
async def repo_harvester_repos():
    return {
        "repos": None,
        "source": "unavailable",
        "data_status": "unavailable",
        "unavailable_reason": "no_verified_repository_inventory",
    }

@app.get("/repo-harvester/reports")
async def repo_harvester_reports():
    p = ROOT / "artifacts" / "repo_harvester"
    if not p.exists():
        return {
            "reports": None,
            "source": "artifacts/repo_harvester",
            "data_status": "unavailable",
            "unavailable_reason": "report_directory_missing",
        }
    return {
        "reports": [f.name for f in p.glob("*.json")],
        "source": "artifacts/repo_harvester",
        "data_status": "stored_file_inventory",
    }

@app.post("/mode/set", dependencies=[Depends(require_operator)])
async def set_mode(payload: dict):
    STATE.set_mode(AccountMode(payload["mode"]))
    logger.info("Mode changed", extra={"component": "dashboard", "mode": STATE.mode.value})
    return {"mode": STATE.mode.value}

@app.post("/kill-switch/enable", dependencies=[Depends(require_operator)])
async def enable_kill_switch(payload: dict):
    STATE.enable_kill_switch(payload.get("reason", "operator"))
    return {"active": True}

@app.post("/kill-switch/disable", dependencies=[Depends(require_operator)])
async def disable_kill_switch():
    STATE.disable_kill_switch()
    return {"active": False}

@app.post("/emergency-stop", dependencies=[Depends(require_operator)])
async def emergency_stop():
    STATE.trigger_emergency_stop()
    return {"active": True}

@app.post("/orders/cancel", dependencies=[Depends(require_operator)])
async def cancel_order(payload: dict):
    # No real cancel path is wired to the dashboard: the sqlite store records
    # paper orders but nothing cancels them, and this app never contacts the
    # broker on its own (that goes through the operator appliance CLI).
    # Fail closed with 501 rather than faking a success.
    raise HTTPException(
        status_code=501,
        detail="order cancel is not wired to any broker/store adapter; "
               "cancel via the operator appliance CLI — no action was taken",
    )

@app.post("/orders/cancel-all", dependencies=[Depends(require_operator)])
async def cancel_all_orders():
    raise HTTPException(
        status_code=501,
        detail="cancel-all is not wired to any broker/store adapter; "
               "use the emergency-stop / operator appliance CLI — no action was taken",
    )

@app.post("/repo-harvester/run", dependencies=[Depends(require_operator)])
async def repo_harvester_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_harvester)
    return {"status": "started"}

@app.post("/repo-harvester/audit-repo", dependencies=[Depends(require_operator)])
async def audit_single_repo(payload: dict):
    return {"status": "not_implemented"}

@app.post("/repo-harvester/build-adapter-plan", dependencies=[Depends(require_operator)])
async def build_adapter_plan(payload: dict):
    return {"status": "not_implemented"}

@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "mode": STATE.mode.value,
                "kill_switch_active": STATE.kill_switch.active,
                "emergency_stop_active": STATE.emergency_stop.active,
                "kalshi_connected": STATE.kalshi_connected,
            })
            await asyncio.sleep(2)
    except Exception:
        pass
