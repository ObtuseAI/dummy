from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from scripts.generate_v16_reports import build_v16_context

router = APIRouter(prefix="/api/v16", tags=["v16"])


async def _context():
    return await asyncio.to_thread(build_v16_context)


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    context = await _context()
    return {
        "mission_state": context.mission_state.to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/dummy_mission_state_report_v1.json"],
    }


@router.get("/real-terrain-truth")
async def real_terrain_truth() -> dict[str, Any]:
    context = await _context()
    return {
        "terrain_truth": context.truth.to_report(),
        "evidence": context.truth.evidence.to_report(),
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/real_terrain_truth_resolver_report_v1.json",
            "artifacts/dummy/real_terrain_truth_evidence_report_v1.json",
        ],
    }


@router.get("/config-binding")
async def config_binding() -> dict[str, Any]:
    context = await _context()
    return {
        "runtime_config": context.runtime_config.to_report(),
        "config_binding": context.config_binding_report,
        "client_factory": context.client_factory_report,
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/kalshi_readonly_runtime_config_report_v1.json",
            "artifacts/dummy/kalshi_readonly_config_binding_proof_v1.json",
            "artifacts/dummy/kalshi_readonly_client_factory_report_v1.json",
        ],
    }


@router.get("/proof-freshness")
async def proof_freshness() -> dict[str, Any]:
    from predator_mesh.v16.proof_freshness import ArtifactDependencyGraph, ProofFreshnessResolver

    context = await _context()
    freshness = ProofFreshnessResolver(
        required_artifacts={
            "real_terrain_truth_resolver_report_v1.json": context.truth.to_report(),
            "orderbook_liquidity_model_report_v6.json": context.liquidity.orderbook_liquidity_model_report_v6(),
            "dummy_mission_state_report_v1.json": context.mission_state.to_report(),
        }
    ).to_report()
    return {
        "proof_freshness": freshness,
        "artifact_dependency_graph": ArtifactDependencyGraph.for_v16().to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/proof_freshness_resolver_report_v1.json"],
    }
