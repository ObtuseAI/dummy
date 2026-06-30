import asyncio, json
from pathlib import Path
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode
from services.sqlite_store import init_db, get_orders, get_positions, insert_order
from repo_harvester.runner import run_harvester
from core.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    log_file = Path("C:/src/engine/dumby/logs/dumby.jsonl")
    lines = []
    if log_file.exists():
        with log_file.open() as f:
            lines = f.readlines()[-limit:]
    return {"logs": [json.loads(l) for l in lines if l.strip()]}

@app.get("/repo-harvester/status")
async def repo_harvester_status():
    return {"status": "idle"}

@app.get("/repo-harvester/repos")
async def repo_harvester_repos():
    return {"repos": []}

@app.get("/repo-harvester/reports")
async def repo_harvester_reports():
    from pathlib import Path
    p = Path("C:/src/engine/dumby/artifacts/repo_harvester")
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
