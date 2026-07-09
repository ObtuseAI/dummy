from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2, RealOrderbookSnapshotClosure
from predator_mesh.v13.repair_packet import KalshiReadOnlyOperatorRepairPacket
from predator_mesh.v13.replay_v2 import RealOrderbookReplayArchive, RealOrderbookReplayQualityScore, RealOrderbookReplayStore
from predator_mesh.v13.runtime_profile import SlowTestAccelerationReport, TestRuntimeProfileReport
from predator_mesh.v13.source_adapter_closure import SourceAdapterClosurePassV2

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v13", tags=["v13"])

_CLOSURE_CACHE: RealOrderbookSnapshotClosure | None = None


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


async def _closure() -> RealOrderbookSnapshotClosure:
    global _CLOSURE_CACHE
    if _CLOSURE_CACHE is None:
        _CLOSURE_CACHE = await RealKalshiOrderbookSnapshotAdapterV2().capture()
    return _CLOSURE_CACHE


def _replay_store(closure: RealOrderbookSnapshotClosure) -> RealOrderbookReplayStore:
    store = RealOrderbookReplayStore()
    store.add_snapshot(closure.snapshot_result)
    return store


@router.get("/kalshi-credential-bridge")
async def kalshi_credential_bridge() -> dict[str, Any]:
    return {
        **KalshiReadOnlyCredentialBridge().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/kalshi_readonly_credential_bridge_report_v1.json",
            "artifacts/dummy/kalshi_credential_source_resolution_report_v1.json",
            "artifacts/dummy/kalshi_credential_redaction_report_v1.json",
        ],
    }


@router.get("/market-discovery")
async def market_discovery() -> dict[str, Any]:
    closure = await _closure()
    return {
        "workstream": "V13: Market Discovery",
        **closure.discovery.to_dict(),
        "candidate_manifest": closure.discovery.candidate_manifest(),
        "mode_report": closure.discovery.to_mode_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/real_kalshi_market_discovery_report_v1.json",
            "artifacts/dummy/eligible_market_candidate_manifest_v1.json",
            "artifacts/dummy/market_discovery_mode_report_v1.json",
        ],
    }


@router.get("/orderbook-snapshot")
async def orderbook_snapshot() -> dict[str, Any]:
    closure = await _closure()
    return {
        **closure.to_report(),
        "mode_report": closure.mode_report(),
        "manifest": closure.manifest(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/real_kalshi_orderbook_snapshot_adapter_report_v2.json",
            "artifacts/dummy/orderbook_snapshot_mode_report_v2.json",
            "artifacts/dummy/real_orderbook_snapshot_manifest_v1.json",
        ],
    }


@router.get("/orderbook-replay")
async def orderbook_replay() -> dict[str, Any]:
    closure = await _closure()
    store = _replay_store(closure)
    return {
        **store.to_report(),
        "archive": RealOrderbookReplayArchive(store).to_report(),
        "quality": RealOrderbookReplayQualityScore(store).to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/real_orderbook_liquidity_replay_report_v2.json",
            "artifacts/dummy/real_orderbook_replay_archive_report_v1.json",
            "artifacts/dummy/liquidity_replay_quality_report_v1.json",
        ],
    }


@router.get("/liquidity-terrain")
async def liquidity_terrain() -> dict[str, Any]:
    closure = await _closure()
    terrain = OrderbookLiquidityTerrainV3(closure.snapshot_result, closure_outcome=closure.outcome)
    return {
        "orderbook_model": terrain.orderbook_model_report(),
        "fill_quality": terrain.fill_quality_report(),
        "stale_quote_risk": terrain.stale_quote_report(),
        "live_liquidity_proof": terrain.live_liquidity_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/orderbook_liquidity_model_report_v3.json",
            "artifacts/dummy/fill_quality_estimate_report_v3.json",
            "artifacts/dummy/stale_quote_risk_report_v3.json",
            "artifacts/dummy/live_liquidity_proof_engine_report_v3.json",
        ],
    }


@router.get("/kalshi-repair-packet")
async def kalshi_repair_packet() -> dict[str, Any]:
    closure = await _closure()
    return {
        **KalshiReadOnlyOperatorRepairPacket(snapshot_closure=closure).to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/kalshi_readonly_operator_repair_packet_v1.json"],
    }


@router.get("/source-adapter-closure")
async def source_adapter_closure() -> dict[str, Any]:
    closure = await _closure()
    source = SourceAdapterClosurePassV2(closure.snapshot_result)
    return {
        **source.to_report(),
        "mode_report": source.mode_report_v3(),
        "remaining_partials": source.remaining_partial_report_v2(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/source_adapter_closure_report_v2.json",
            "artifacts/dummy/source_adapter_mode_report_v3.json",
            "artifacts/dummy/source_adapter_remaining_partial_report_v2.json",
        ],
    }


@router.get("/test-runtime-profile")
async def test_runtime_profile() -> dict[str, Any]:
    return {
        "runtime_profile": TestRuntimeProfileReport().to_report(),
        "slow_test_acceleration": SlowTestAccelerationReport().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/test_runtime_profile_report_v1.json",
            "artifacts/dummy/slow_test_acceleration_report_v1.json",
        ],
    }
