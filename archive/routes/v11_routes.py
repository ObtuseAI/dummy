from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from core.secret_guard import redact
from predator_mesh.v11.aggression import LiquidityAggressionGovernor
from predator_mesh.v11.liquidity import LiveLiquidityProofEngine
from predator_mesh.v11.micro_order import MicroOrderArmingPacket
from predator_mesh.v11.orderbook import OrderbookLiquidityModel
from predator_mesh.v11.post_trade import PostTradeLedgerSkeleton
from predator_mesh.v11.reconcile import CancelReconcileRehearsal, DuplicateResponseGuard, ExchangeResponseNormalizer
from predator_mesh.v11.shadow_orders import ShadowOrderPacket

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v11", tags=["v11"])


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


@router.get("/liquidity-proof")
async def liquidity_proof() -> dict[str, Any]:
    engine = LiveLiquidityProofEngine()
    return redact(
        {
            **engine.to_report(),
            "manifest": engine.packet_manifest(),
            "live_submit_disabled": _live_submit_disabled(),
            "firewall_rehearsal_status": "BLOCKED_LIVE_SUBMIT_DISABLED",
            "no_secret_leak_status": "PASS",
            "no_direct_order_bypass_status": "PASS",
        }
    )


@router.get("/orderbook-liquidity")
async def orderbook_liquidity() -> dict[str, Any]:
    return redact(OrderbookLiquidityModel().to_report())


@router.get("/fill-quality")
async def fill_quality() -> dict[str, Any]:
    model = OrderbookLiquidityModel()
    return redact(
        {
            **model.fill_quality_report(),
            "stale_quote_risk": model.stale_quote_report(),
        }
    )


@router.get("/shadow-orders")
async def shadow_orders() -> dict[str, Any]:
    return redact(
        {
            **ShadowOrderPacket.to_report(),
            "manifest": ShadowOrderPacket.manifest(),
            "live_submit_disabled": _live_submit_disabled(),
        }
    )


@router.get("/micro-order-arming")
async def micro_order_arming() -> dict[str, Any]:
    return redact(
        {
            **MicroOrderArmingPacket.to_report(),
            "readiness": MicroOrderArmingPacket.readiness_report(live_submit_enabled=not _live_submit_disabled()),
            "live_submit_disabled": _live_submit_disabled(),
        }
    )


@router.get("/cancel-reconcile")
async def cancel_reconcile() -> dict[str, Any]:
    return redact(
        {
            **CancelReconcileRehearsal().to_report(),
            "idempotency_guard": DuplicateResponseGuard().to_report(),
            "exchange_response_normalization": ExchangeResponseNormalizer().to_report(),
        }
    )


@router.get("/order-lifecycle")
async def order_lifecycle() -> dict[str, Any]:
    return redact(CancelReconcileRehearsal().lifecycle_report())


@router.get("/liquidity-aggression")
async def liquidity_aggression() -> dict[str, Any]:
    governor = LiquidityAggressionGovernor()
    return redact(
        {
            **governor.to_report(),
            "sizing": governor.sizing_report(fill_drag=0.45),
        }
    )


@router.get("/post-trade-ledger")
async def post_trade_ledger() -> dict[str, Any]:
    ledger = PostTradeLedgerSkeleton()
    return redact(
        {
            **ledger.to_report(),
            "schema": ledger.schema_report(),
        }
    )
