from __future__ import annotations
from fastapi import APIRouter
from core.state import STATE
from core.ontology import AccountMode, OrderBook, OrderBookLevel
from forecasting.hybrid_engine import HybridForecastEngine
from strategies.intelligence import StrategyIntelligence
from execution.hybrid_path import HybridAutonomousExecutionPath
from archive.routes.v6_routes import identity as v6_identity
from datetime import datetime, timezone

router = APIRouter(prefix="/v7", tags=["v7"])

@router.get("/identity")
async def identity():
    v6 = await v6_identity()
    return {
        "project": "Dummy",
        "milestone": "DUMMY_V7_HYBRID_ROUTING_DESIGN_V1",
        "previous_name": v6["previous_name"],
        "v7_focus": "hybrid_model_routing",
    }

@router.get("/model-router/status")
async def model_router_status():
    from model_router.config import load_model_routing_config
    cfg = load_model_routing_config()
    return {
        "config_present": True,
        "mock_fallback_enabled": cfg.mock_fallback_enabled,
        "blocked_categories": cfg.blocked_prompt_categories,
    }

@router.get("/forecast/opinion")
async def forecast_opinion(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    engine = HybridForecastEngine()
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    opinion = await engine.forecast_opinion(market_ticker, contract_ticker, market_ticker, contract_ticker, book)
    return {"opinion": opinion.model_dump(), "source": "mock"}

@router.get("/strategies/intelligence")
async def strategies_intelligence(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    intel = StrategyIntelligence()
    from forecasting.engine import ForecastEngine
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = ForecastEngine().forecast(market_ticker, contract_ticker, market_ticker, contract_ticker, book)
    results = await intel.evaluate(forecast, book)
    return {"results": [r.scan_result.family for r in results], "source": "mock"}

@router.get("/hybrid/rehearsal")
async def hybrid_rehearsal(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    if STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
        return {"status": "blocked", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED"}
    path = HybridAutonomousExecutionPath()
    result = await path.rehearse_live_cap_with_model_review(market_ticker, contract_ticker)
    return {"status": result.get("status"), "model_review_present": result.get("model_review") is not None}

@router.get("/reports/status")
async def reports_status():
    from pathlib import Path
    final = Path("C:/src/engine/dummy/artifacts/dummy/final_report.json")
    return {"final_report_present": final.exists()}
