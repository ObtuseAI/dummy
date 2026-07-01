import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode, OrderBook, OrderBookLevel
from forecasting.engine import ForecastEngine
from services.sqlite_store import init_db, get_orders, get_positions, insert_order
from repo_harvester.runner import run_harvester
from repo_harvester.manifest import REPOS_V2
from core.logger import logger
from dashboard.backend.v3_routes import router as v3_router
from dashboard.backend.v4_routes import router as v4_router
from dashboard.backend.v5_routes import router as v5_router
from dashboard.backend.v6_routes import router as v6_router
from dashboard.backend import v7_routes
from dashboard.backend import v8_routes
from dashboard.backend import v9_routes
from model_router.credential_source import (
    ProviderCredentialReadinessV2,
    ProviderCredentialSourceResolver,
)
from model_router.resolver import ModelProviderResolver, _DEFAULT_ALIASES, _DEFAULT_BASE_URLS
from model_router.route_mode import ProviderRouteModeResolver
from model_router.smoke import (
    _DEEPSEEK_SMOKE_PROMPT,
    _MINIMAX_SMOKE_PROMPT,
    LiveModelSmokeV3,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(v3_router)
app.include_router(v4_router)
app.include_router(v5_router)
app.include_router(v6_router)
app.include_router(v7_routes.router)
app.include_router(v8_routes.router)
app.include_router(v9_routes.router)

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

ARTIFACTS = Path("C:/src/engine/dummy/artifacts/repo_harvester")
DUMMY_ARTIFACTS = Path("C:/src/engine/dummy/artifacts/dummy")
ROOT = Path("C:/src/engine/dummy")


def _load_artifact(filename: str) -> dict:
    path = ARTIFACTS / filename
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


@app.get("/markets")
async def markets():
    caps = load_caps()
    return {
        "allowed_markets": caps.allowed_markets,
        "blocked_categories": caps.blocked_categories,
        "market_categories": [g["display_name"] for g in REPOS_V2],
    }


@app.get("/forecasts")
async def forecasts():
    engine = ForecastEngine()
    book = OrderBook(
        market_ticker="WEATHER-NYC-RAIN",
        contract_ticker="WEATHER-NYC-RAIN-YES",
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    return {
        "forecasts": [
            engine.forecast(
                "WEATHER-NYC-RAIN",
                "WEATHER-NYC-RAIN-YES",
                "NYC Rain",
                "Yes",
                book,
            ).model_dump(),
        ],
    }


@app.get("/strategies")
async def strategies():
    from strategies.registry import STRATEGIES
    candidates = _load_artifact("strategy_extraction_report_v1.json").get("candidates", [])
    return {
        "registered_strategies": [s.__class__.__name__ for s in STRATEGIES],
        "repo_derived_candidates": candidates,
    }

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
    log_file = Path("C:/src/engine/dummy/logs/dummy.jsonl")
    lines = []
    if log_file.exists():
        with log_file.open() as f:
            lines = f.readlines()[-limit:]
    return {"logs": [json.loads(l) for l in lines if l.strip()]}

@app.get("/repo-harvester/status")
async def repo_harvester_status():
    summary = _load_artifact("source_scan_summary_v1.json")
    bypass = _load_artifact("firewall_bypass_scan_report_v1.json")
    plan = _load_artifact("adapter_plan_v3.json")
    rejected = _load_artifact("rejected_repo_report_v3.json")
    return {
        "v2_source_scan": {
            "repos_in_manifest": summary.get("repos_in_manifest", 0),
            "repos_scanned": summary.get("repos_scanned", 0),
            "total_files_scanned": summary.get("total_files_scanned", 0),
            "verdict_counts": summary.get("verdict_counts", {}),
            "finding_category_repo_counts": summary.get("finding_category_repo_counts", {}),
        },
        "adapters": {
            "accepted": plan.get("accepted_count", 0),
            "direct_dependency": plan.get("direct_dependency_count", 0),
            "adapter_target": plan.get("adapter_target_count", 0),
            "rejected": rejected.get("rejected_count", 0),
        },
        "firewall_bypass_findings": {
            "direct_order_count": bypass.get("direct_order_count", 0),
            "secret_risk_count": bypass.get("secret_risk_count", 0),
        },
        "live_firewall_status": {
            "mode": STATE.mode.value,
            "kill_switch_active": STATE.kill_switch.active,
            "emergency_stop_active": STATE.emergency_stop.active,
        },
        "blocked_order_reasons": list(set(
            hit["repo"] for hit in bypass.get("direct_order_repos", [])
        ) | set(
            hit["repo"] for hit in bypass.get("secret_risk_repos", [])
        )),
    }


@app.get("/repo-harvester/repos")
async def repo_harvester_repos():
    plan = _load_artifact("adapter_plan_v3.json")
    rejected = _load_artifact("rejected_repo_report_v3.json")
    return {
        "accepted_adapters": [
            {"repo": p["repo"], "category": p["category"], "verdict": p["verdict"], "adapter": pl["adapter_name"]}
            for p in plan.get("plans", [])
            for pl in p.get("plans", [])
        ],
        "rejected_repos": [
            {"repo": p["repo"], "category": p["category"], "verdict": p["verdict"], "reasons": p.get("verdict_reasons", [])}
            for p in rejected.get("rejected", [])
        ],
    }


@app.get("/repo-harvester/reports")
async def repo_harvester_reports():
    files = [f.name for f in ARTIFACTS.glob("*.json")] if ARTIFACTS.exists() else []
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

@app.get("/api/v8/model-provider-resolution")
async def model_provider_resolution():
    """Return redacted live-model provider resolution status for V8.1/V8.2 dashboard."""
    resolver = ModelProviderResolver()
    ds, mm = await asyncio.gather(
        asyncio.wait_for(
            resolver.resolve(
                "deepseek_v4_flash",
                default_base=_DEFAULT_BASE_URLS["deepseek_v4_flash"],
                default_aliases=_DEFAULT_ALIASES["deepseek_v4_flash"],
                smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
            ),
            timeout=45.0,
        ),
        asyncio.wait_for(
            resolver.resolve(
                "minimax_m3",
                default_base=_DEFAULT_BASE_URLS["minimax_m3"],
                default_aliases=_DEFAULT_ALIASES["minimax_m3"],
                smoke_prompt=_MINIMAX_SMOKE_PROMPT,
            ),
            timeout=45.0,
        ),
    )
    return {
        "deepseek_v4_flash": ds.redacted_metadata,
        "minimax_m3": mm.redacted_metadata,
        "repair_recommendation_path": str(ROOT / "artifacts" / "dummy" / "model_provider_operator_repair_recommendations_v1.json"),
        "repair_packet_path": str(ROOT / "artifacts" / "dummy" / "provider_operator_repair_packet_v1.json"),
    }


@app.get("/api/v8/provider-credential-source")
async def provider_credential_source():
    """Return redacted credential source for each provider."""
    readiness = ProviderCredentialReadinessV2()
    return {
        "deepseek_v4_flash": readiness.deepseek_status().as_dict(),
        "minimax_m3": readiness.minimax_status().as_dict(),
        "openrouter": readiness.openrouter_status().as_dict(),
    }


@app.get("/api/v8/provider-route-mode")
async def provider_route_mode():
    """Return redacted route-mode resolution for each provider."""
    credential_resolver = ProviderCredentialSourceResolver()
    route_resolver = ProviderRouteModeResolver(credential_resolver)
    resolver = ModelProviderResolver()
    result: dict[str, Any] = {}
    for name in ("deepseek_v4_flash", "minimax_m3"):
        candidate = resolver._endpoint_candidate(name, _DEFAULT_BASE_URLS.get(name, ""))
        configured = resolver._configured_model(name)
        result[name] = route_resolver.resolve(name, candidate.api_base, configured).as_dict()
    return result


@app.get("/api/v8/live-model-proof")
async def live_model_proof():
    """Return V8.2 live-model proof status with bounded timeout."""
    smoke = LiveModelSmokeV3()
    try:
        report = await asyncio.wait_for(smoke.run(), timeout=50.0)
    except asyncio.TimeoutError:
        report = {
            "live_model_status": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "model_mode": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "error": "dashboard live-model-proof handler timed out",
        }
    return {
        "live_model_status": report.get("live_model_status"),
        "model_mode": report.get("model_mode"),
        "verdict": report.get("verdict"),
        "call_results": report.get("call_results", []),
    }


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
