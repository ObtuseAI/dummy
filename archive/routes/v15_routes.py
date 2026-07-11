from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v15.auth_probe_v2 import KalshiAuthProbeV2
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from predator_mesh.v15.launch_readiness_v2 import LiquidityLaunchReadinessMatrixV2
from predator_mesh.v15.normalization_preview import KalshiCredentialNormalizationPreview
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.runtime_acceleration_v2 import (
    RuntimeAccelerationMegaReportV2,
    SlowTestRemediationReportV2,
    TestRuntimeBudgetReportV2,
)
from predator_mesh.v15.source_adapter_closure_v5 import SourceAdapterClosureV5
from predator_mesh.v15.terrain_closure_v3 import RealOrderbookTerrainClosureV3

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v15", tags=["v15"])


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


def _forensics() -> dict[str, Any]:
    return KalshiCredentialForensics().to_report()


def _shape_engine() -> KalshiCredentialShapeRepairEngine:
    return KalshiCredentialShapeRepairEngine()


def _conflict_resolver() -> KalshiCredentialSourceConflictResolver:
    return KalshiCredentialSourceConflictResolver()


@router.get("/credential-shape-repair")
async def credential_shape_repair() -> dict[str, Any]:
    return {
        "shape_repair": _shape_engine().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/kalshi_credential_shape_repair_report_v1.json"],
    }


@router.get("/credential-source-conflicts")
async def credential_source_conflicts() -> dict[str, Any]:
    return {
        "conflict_resolution": _conflict_resolver().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/kalshi_credential_source_conflict_report_v1.json"],
    }


@router.get("/normalization-preview")
async def normalization_preview() -> dict[str, Any]:
    return {
        "preview": KalshiCredentialNormalizationPreview(repair_engine=_shape_engine()).to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/kalshi_credential_normalization_preview_report_v1.json"],
    }


@router.get("/auth-probe-v2")
async def auth_probe_v2() -> dict[str, Any]:
    import asyncio

    probe = KalshiAuthProbeV2(repair_engine=_shape_engine(), conflict_resolver=_conflict_resolver())
    # to_report() may call asyncio.run() internally (bounded probe_fn); run it
    # off-thread so it never collides with this endpoint's own running loop.
    report = await asyncio.to_thread(probe.to_report)
    return {
        "auth_probe": report,
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/kalshi_auth_probe_v2_report_v1.json"],
    }


@router.get("/real-terrain-retry-v2")
async def real_terrain_retry_v2() -> dict[str, Any]:
    forensics = _forensics()
    gate = RealTerrainRetryGateV2(forensics_report=forensics)
    return {
        "retry_gate": gate.to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/real_terrain_retry_gate_v2_report_v1.json"],
    }


@router.get("/real-orderbook-terrain-v3")
async def real_orderbook_terrain_v3() -> dict[str, Any]:
    import asyncio

    forensics = _forensics()
    closure = RealOrderbookTerrainClosureV3(forensics_report=forensics)
    # to_report() may reach a sync snapshot capture that calls asyncio.run()
    # internally; run off-thread to avoid colliding with this running loop.
    report = await asyncio.to_thread(closure.to_report)
    return {
        "terrain": report,
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/real_orderbook_terrain_closure_v3_report_v1.json"],
    }


@router.get("/liquidity-launch-gate-v2")
async def liquidity_launch_gate_v2() -> dict[str, Any]:
    import asyncio

    forensics = _forensics()
    readiness = LiquidityLaunchReadinessMatrixV2(forensics_report=forensics)
    # Transitively reaches the same sync/asyncio.run() snapshot path as
    # real_orderbook_terrain_v3; run off-thread for the same reason.
    report = await asyncio.to_thread(readiness.to_report)
    return {
        "matrix": report,
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/liquidity_launch_readiness_matrix_v2_report_v1.json"],
    }


@router.get("/source-adapter-closure-v5")
async def source_adapter_closure_v5() -> dict[str, Any]:
    import asyncio

    forensics = _forensics()
    closure = SourceAdapterClosureV5(forensics_report=forensics)
    # Transitively reaches the same sync/asyncio.run() snapshot path as
    # real_orderbook_terrain_v3; run off-thread for the same reason.
    report = await asyncio.to_thread(closure.to_report)
    return {
        "closure": report,
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": ["artifacts/dummy/source_adapter_closure_v5_report_v1.json"],
    }


@router.get("/runtime-acceleration-v2")
async def runtime_acceleration_v2() -> dict[str, Any]:
    return {
        "runtime_acceleration": RuntimeAccelerationMegaReportV2().to_report(),
        "test_runtime_budget": TestRuntimeBudgetReportV2().to_report(),
        "slow_test_remediation": SlowTestRemediationReportV2().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }
