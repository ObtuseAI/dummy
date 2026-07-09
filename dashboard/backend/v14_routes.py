from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix
from predator_mesh.v14.micro_order_dry_run import MicroOrderDryRunBlockerReport, MicroOrderDryRunPacketV2
from predator_mesh.v14.no_trade_gates import FillDragNoTradeReport, LiquidityNoTradeGate, StaleQuoteNoTradeReport
from predator_mesh.v14.repair_wizard import KalshiOperatorRepairWizard, KalshiReadOnlyRetestPlan
from predator_mesh.v14.retry_gate import RealTerrainRetryGate
from predator_mesh.v14.runtime_acceleration import RuntimeAccelerationMegaReport, SlowTestRemediationReport, TestRuntimeBudgetReport
from predator_mesh.v14.source_adapter_promotion import SourceAdapterLegalityRecheck, SourceAdapterPromotionMegaPass
from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v14", tags=["v14"])


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


@router.get("/kalshi-forensics")
async def kalshi_forensics() -> dict[str, Any]:
    forensics = KalshiCredentialForensics()
    return {
        "forensics": forensics.to_report(),
        "private_key_shape": forensics.private_key_shape_report(),
        "auth_probe_classifier": forensics.auth_probe_classifier_report(),
        "repair_hints": forensics.repair_hints_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/kalshi_credential_forensics_report_v1.json",
            "artifacts/dummy/kalshi_private_key_shape_report_v1.json",
            "artifacts/dummy/kalshi_auth_probe_classifier_report_v1.json",
            "artifacts/dummy/kalshi_credential_repair_hints_report_v1.json",
        ],
    }


@router.get("/kalshi-repair-wizard")
async def kalshi_repair_wizard() -> dict[str, Any]:
    forensics = _forensics()
    return {
        "repair_wizard": KalshiOperatorRepairWizard(forensics_report=forensics).to_report(),
        "retest_plan": KalshiReadOnlyRetestPlan().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/kalshi_operator_repair_wizard_packet_v1.json",
            "artifacts/dummy/kalshi_readonly_retest_plan_v1.json",
        ],
    }


@router.get("/real-terrain-retry")
async def real_terrain_retry() -> dict[str, Any]:
    forensics = _forensics()
    gate = RealTerrainRetryGate(forensics_report=forensics)
    return {
        "retry_gate": gate.to_report(),
        "readiness_state": gate.readiness_state().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
        "proof_paths": [
            "artifacts/dummy/real_terrain_retry_gate_report_v1.json",
            "artifacts/dummy/real_terrain_readiness_state_report_v1.json",
        ],
    }


@router.get("/real-terrain-closure")
async def real_terrain_closure() -> dict[str, Any]:
    closure = RealOrderbookTerrainClosureV2(forensics_report=_forensics())
    await closure.resolve_async()
    return {
        "snapshot": closure.snapshot_report(),
        "snapshot_mode": closure.snapshot_mode_report(),
        "manifest": closure.snapshot_manifest(),
        "replay": closure.replay_report(),
        "liquidity_model": closure.liquidity_model_report(),
        "fill_quality": closure.fill_quality_report(),
        "stale_quote": closure.stale_quote_report(),
        "live_liquidity": closure.live_liquidity_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }


@router.get("/source-adapter-promotion")
async def source_adapter_promotion() -> dict[str, Any]:
    forensics = _forensics()
    closure = RealOrderbookTerrainClosureV2(forensics_report=forensics)
    await closure.resolve_async()
    source = SourceAdapterPromotionMegaPass(forensics_report=forensics, terrain_closure=closure)
    return {
        "promotion": source.to_report(),
        "mode_report": source.mode_report_v4(),
        "remaining_partials": source.remaining_partial_report_v3(),
        "legality": SourceAdapterLegalityRecheck().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }


@router.get("/liquidity-launch-readiness")
async def liquidity_launch_readiness() -> dict[str, Any]:
    readiness = LiquidityLaunchReadinessMatrix(forensics_report=_forensics())
    return {
        "matrix": readiness.to_report(),
        "blockers": readiness.blocker_report(),
        "operator_readiness": readiness.operator_readiness_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }


@router.get("/micro-order-dry-run")
async def micro_order_dry_run() -> dict[str, Any]:
    forensics = _forensics()
    return {
        "packet": MicroOrderDryRunPacketV2(forensics_report=forensics).to_report(),
        "blockers": MicroOrderDryRunBlockerReport(forensics_report=forensics).to_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }


@router.get("/liquidity-no-trade-gates")
async def liquidity_no_trade_gates() -> dict[str, Any]:
    forensics = _forensics()
    return {
        "liquidity_no_trade": LiquidityNoTradeGate(forensics_report=forensics).to_report(),
        "fill_drag_no_trade": FillDragNoTradeReport().to_report(),
        "stale_quote_no_trade": StaleQuoteNoTradeReport().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }


@router.get("/runtime-acceleration")
async def runtime_acceleration() -> dict[str, Any]:
    return {
        "runtime_acceleration": RuntimeAccelerationMegaReport().to_report(),
        "test_runtime_budget": TestRuntimeBudgetReport().to_report(),
        "slow_test_remediation": SlowTestRemediationReport().to_report(),
        "live_submit_disabled": _live_submit_disabled(),
    }
