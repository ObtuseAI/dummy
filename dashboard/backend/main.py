import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode
from services.sqlite_store import init_db, get_orders, get_positions
from repo_harvester.runner import run_harvester
from core.logger import logger
from core.secret_guard import redact
from model_router.credential_source import ProviderCredentialSourceResolver
from model_router.resolver import (
    ModelProviderResolver,
    _DEFAULT_ALIASES,
    _DEFAULT_BASE_URLS,
)
from model_router.route_mode import ProviderRouteModeResolver
from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT

ROOT = Path(__file__).resolve().parents[2]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Historical staged-gate report routers (V3-V304) live in archive/routes.
# Each exposes a distinct /api/vNN prefix; mount whatever the archive holds.
import importlib  # noqa: E402
import pkgutil  # noqa: E402
import archive.routes  # noqa: E402
for _module_info in sorted(pkgutil.iter_modules(archive.routes.__path__), key=lambda m: m.name):
    _module = importlib.import_module(f"archive.routes.{_module_info.name}")
    _router = getattr(_module, "router", None)
    if _router is not None:
        app.include_router(_router)

from dashboard.backend import operator_routes  # noqa: E402
from dashboard.backend import operator_control_routes  # noqa: E402
from dashboard.backend import vnext_routes  # noqa: E402
app.include_router(operator_routes.router)
app.include_router(operator_control_routes.router)
app.include_router(vnext_routes.router)

@app.get("/status")
async def status():
    return {
        "mode": STATE.mode.value,
        "kill_switch_active": STATE.kill_switch.active,
        "emergency_stop_active": STATE.emergency_stop.active,
        "kalshi_connected": STATE.kalshi_connected,
        "balance_cents": STATE.balance_cents,
        "daily_loss_cents": STATE.daily_loss_cents,
        "total_exposure_cents": 0,
        "open_positions": await get_positions(),
        "open_orders": await get_orders(),
    }

@app.get("/api/v8/model-provider-resolution")
async def api_v8_model_provider_resolution():
    resolver = ModelProviderResolver()
    deepseek = await resolver.resolve(
        "deepseek_v4_flash",
        default_base=_DEFAULT_BASE_URLS["deepseek_v4_flash"],
        default_aliases=_DEFAULT_ALIASES["deepseek_v4_flash"],
        smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
    )
    minimax = await resolver.resolve(
        "minimax_m3",
        default_base=_DEFAULT_BASE_URLS["minimax_m3"],
        default_aliases=_DEFAULT_ALIASES["minimax_m3"],
        smoke_prompt=_MINIMAX_SMOKE_PROMPT,
    )
    repair_path = ROOT / "artifacts" / "dummy" / "model_provider_operator_repair_recommendations_v1.json"
    return redact(
        {
            "deepseek_v4_flash": deepseek.redacted_metadata,
            "minimax_m3": minimax.redacted_metadata,
            "repair_recommendation_path": str(repair_path),
        }
    )

@app.get("/api/v8/provider-credential-source")
async def api_v8_provider_credential_source():
    credential_resolver = ProviderCredentialSourceResolver()
    route_resolver = ProviderRouteModeResolver(credential_resolver)
    resolver = ModelProviderResolver()
    data = {}
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        candidate = resolver._endpoint_candidate(provider, _DEFAULT_BASE_URLS[provider])
        route = route_resolver.resolve(
            provider,
            candidate.api_base,
            resolver._configured_model(provider),
        )
        credential = credential_resolver.resolve(route.intended_key_env)
        data[provider] = {
            "api_key_env": route.intended_key_env,
            "source": credential.source.value,
            "present": credential.present,
            "route_mode": route.route_mode.value,
            "base_url_class": route.base_url_class,
        }
    openrouter = credential_resolver.resolve("OPENROUTER_API_KEY")
    data["openrouter"] = {
        "api_key_env": "OPENROUTER_API_KEY",
        "source": openrouter.source.value,
        "present": openrouter.present,
        "route_mode": "openrouter",
    }
    return redact(data)

@app.get("/api/v8/provider-route-mode")
async def api_v8_provider_route_mode():
    credential_resolver = ProviderCredentialSourceResolver()
    route_resolver = ProviderRouteModeResolver(credential_resolver)
    resolver = ModelProviderResolver()
    data = {}
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        candidate = resolver._endpoint_candidate(provider, _DEFAULT_BASE_URLS[provider])
        route = route_resolver.resolve(
            provider,
            candidate.api_base,
            resolver._configured_model(provider),
        )
        data[provider] = route.as_dict()
    return redact(data)

@app.get("/api/v8/live-model-proof")
async def api_v8_live_model_proof():
    smoke_path = ROOT / "artifacts" / "dummy" / "live_model_smoke_report_v3.json"
    if smoke_path.exists():
        try:
            smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        except Exception:
            smoke = {}
    else:
        smoke = {}
    return redact(
        {
            "live_model_status": smoke.get("live_model_status", "UNKNOWN"),
            "model_mode": smoke.get("model_mode", "UNKNOWN"),
            "verdict": smoke.get("verdict", "PASS"),
        }
    )

@app.get("/markets")
async def markets():
    return {"markets": []}

@app.get("/forecasts")
async def forecasts():
    return {"forecasts": []}

@app.get("/strategies")
async def strategies():
    return {"strategies": []}

@app.get("/orders")
async def orders():
    return {"orders": await get_orders()}

@app.get("/positions")
async def positions():
    return {"positions": await get_positions()}

@app.get("/risk")
async def risk():
    return {"caps": load_caps().model_dump(), "daily_loss_cents": STATE.daily_loss_cents}

@app.get("/proof")
async def proof():
    return {"proofs": []}

@app.get("/logs")
async def logs(limit: int = 100):
    log_file = ROOT / "logs" / "dummy.jsonl"
    lines = []
    if log_file.exists():
        with log_file.open() as f:
            lines = f.readlines()[-limit:]
    return {"logs": [json.loads(line) for line in lines if line.strip()]}

@app.get("/repo-harvester/status")
async def repo_harvester_status():
    return {"status": "idle"}

@app.get("/repo-harvester/repos")
async def repo_harvester_repos():
    return {"repos": []}

@app.get("/repo-harvester/reports")
async def repo_harvester_reports():
    p = ROOT / "artifacts" / "repo_harvester"
    files = [f.name for f in p.glob("*.json")] if p.exists() else []
    return {"reports": files}

@app.post("/mode/set")
async def set_mode(payload: dict):
    STATE.set_mode(AccountMode(payload["mode"]))
    logger.info("Mode changed", extra={"component": "dashboard", "mode": STATE.mode.value})
    return {"mode": STATE.mode.value}

@app.post("/kill-switch/enable")
async def enable_kill_switch(payload: dict):
    STATE.enable_kill_switch(payload.get("reason", "operator"))
    return {"active": True}

@app.post("/kill-switch/disable")
async def disable_kill_switch():
    STATE.disable_kill_switch()
    return {"active": False}

@app.post("/emergency-stop")
async def emergency_stop():
    STATE.trigger_emergency_stop()
    return {"active": True}

@app.post("/orders/cancel")
async def cancel_order(payload: dict):
    return {"cancelled": payload["order_id"]}

@app.post("/orders/cancel-all")
async def cancel_all_orders():
    return {"cancelled": "all"}

@app.post("/repo-harvester/run")
async def repo_harvester_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_harvester)
    return {"status": "started"}

@app.post("/repo-harvester/audit-repo")
async def audit_single_repo(payload: dict):
    return {"status": "not_implemented"}

@app.post("/repo-harvester/build-adapter-plan")
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
