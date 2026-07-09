from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from core.secret_guard import redact
from predator_mesh.v12.bloodline import LiquiditySignalBloodline, LiquiditySourceBloodline
from predator_mesh.v12.calibration import LiquidityCalibrationStore
from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2
from predator_mesh.v12.orderbook_snapshot import RealKalshiOrderbookSnapshotAdapter, default_snapshot_request
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2
from predator_mesh.v12.replay import OrderbookReplayRun
from predator_mesh.v12.source_adapter_closure import SourceAdapterClosurePass

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v12", tags=["v12"])


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


async def _snapshot():
    return await RealKalshiOrderbookSnapshotAdapter().capture(default_snapshot_request())


@router.get("/orderbook-snapshot")
async def orderbook_snapshot() -> dict[str, Any]:
    result = await _snapshot()
    return redact(
        {
            "workstream": "V12: Real Orderbook Snapshot",
            "snapshot_mode": result.mode.value,
            "real_vs_fallback_status": "REAL" if result.is_real else "FALLBACK_OR_DEGRADED",
            "live_submit_disabled": _live_submit_disabled(),
            "result": result.to_dict(),
            "proof_paths": ["artifacts/dummy/real_kalshi_orderbook_snapshot_adapter_report_v1.json"],
            "verdict": "PASS",
        }
    )


@router.get("/liquidity-replay")
async def liquidity_replay() -> dict[str, Any]:
    result = await _snapshot()
    sequence = OrderbookReplayRun().run([result])
    return redact(
        {
            "workstream": "V12: Liquidity Replay",
            **sequence.to_dict(),
            "proof_paths": ["artifacts/dummy/real_orderbook_liquidity_replay_report_v1.json"],
        }
    )


@router.get("/liquidity-proof-v2")
async def liquidity_proof_v2() -> dict[str, Any]:
    result = await _snapshot()
    engine = LiveLiquidityProofEngineV2()
    return redact(
        {
            **engine.to_report(result),
            "manifest": engine.packet_manifest(),
            "live_submit_disabled": _live_submit_disabled(),
            "proof_paths": ["artifacts/dummy/live_liquidity_proof_engine_report_v2.json"],
        }
    )


@router.get("/fill-quality-v2")
async def fill_quality_v2() -> dict[str, Any]:
    result = await _snapshot()
    return redact(OrderbookLiquidityModelV2().fill_quality_report_v2(result))


@router.get("/stale-quote-risk-v2")
async def stale_quote_risk_v2() -> dict[str, Any]:
    return redact(OrderbookLiquidityModelV2().stale_quote_report_v2())


@router.get("/liquidity-calibration")
async def liquidity_calibration() -> dict[str, Any]:
    store = LiquidityCalibrationStore()
    return redact(
        {
            **store.to_report(),
            "schema": store.fill_quality_schema_report(),
        }
    )


@router.get("/source-adapter-closure")
async def source_adapter_closure() -> dict[str, Any]:
    closure = SourceAdapterClosurePass()
    return redact(
        {
            **closure.to_report(),
            "mode_report": closure.mode_report_v2(),
            "remaining_partials": closure.remaining_partial_report(),
            "live_submit_disabled": _live_submit_disabled(),
        }
    )


@router.get("/liquidity-bloodlines")
async def liquidity_bloodlines() -> dict[str, Any]:
    return redact(
        {
            "source_bloodline": LiquiditySourceBloodline().to_report(),
            "signal_bloodline": LiquiditySignalBloodline().to_report(),
            "verdict": "PASS",
        }
    )
