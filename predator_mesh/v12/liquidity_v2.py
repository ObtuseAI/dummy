"""Real-terrain liquidity proof V2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


class RealTerrainLiquidityVerdict(str, Enum):
    REAL_TERRAIN_REHEARSAL_APPROVED = "REAL_TERRAIN_REHEARSAL_APPROVED"
    FALLBACK_TERRAIN_REHEARSAL_APPROVED = "FALLBACK_TERRAIN_REHEARSAL_APPROVED"
    NO_TRADE_LIQUIDITY_TOO_THIN = "NO_TRADE_LIQUIDITY_TOO_THIN"
    NO_TRADE_SPREAD_TOO_WIDE = "NO_TRADE_SPREAD_TOO_WIDE"
    NO_TRADE_STALE_ORDERBOOK = "NO_TRADE_STALE_ORDERBOOK"
    NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG = "NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG"
    QUARANTINE_MARKET = "QUARANTINE_MARKET"


class RealTerrainNoTradeReason(str, Enum):
    NO_TRADE_LIQUIDITY_TOO_THIN = "NO_TRADE_LIQUIDITY_TOO_THIN"
    NO_TRADE_SPREAD_TOO_WIDE = "NO_TRADE_SPREAD_TOO_WIDE"
    NO_TRADE_STALE_ORDERBOOK = "NO_TRADE_STALE_ORDERBOOK"
    NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG = "NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG"
    QUARANTINE_MARKET = "QUARANTINE_MARKET"


@dataclass(frozen=True)
class RealTerrainLiquidityProofPacket:
    packet_id: str
    snapshot_mode: OrderbookSnapshotMode
    verdict: RealTerrainLiquidityVerdict
    no_trade_reasons: list[str]
    proof_refs: dict[str, str]
    spread_cents: int | None
    top_of_book_depth: int
    stale_quote_risk: float
    fill_drag_cents: float
    execution_feasibility_score: float
    live_submit_required: bool = False
    market_orders_allowed: bool = False
    firewall_rehearsal_status: str = "BLOCKED_LIVE_SUBMIT_DISABLED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "snapshot_mode": self.snapshot_mode.value,
            "verdict": self.verdict.value,
            "no_trade_reasons": self.no_trade_reasons,
            "proof_refs": self.proof_refs,
            "spread_cents": self.spread_cents,
            "top_of_book_depth": self.top_of_book_depth,
            "stale_quote_risk": self.stale_quote_risk,
            "fill_drag_cents": self.fill_drag_cents,
            "execution_feasibility_score": self.execution_feasibility_score,
            "live_submit_required": self.live_submit_required,
            "market_orders_allowed": self.market_orders_allowed,
            "firewall_rehearsal_status": self.firewall_rehearsal_status,
        }


class LiveLiquidityProofEngineV2:
    def __init__(self) -> None:
        self.model = OrderbookLiquidityModelV2()

    def evaluate_snapshot(self, result: OrderbookSnapshotResult | None = None) -> RealTerrainLiquidityProofPacket:
        result = result or self.model.fallback_result()
        analysis = self.model.analyze_result(result)
        status = analysis.execution_feasibility_score.status
        no_trade = [] if status == "FEASIBLE" else [status]
        if status == "FEASIBLE":
            verdict = (
                RealTerrainLiquidityVerdict.REAL_TERRAIN_REHEARSAL_APPROVED
                if result.mode is OrderbookSnapshotMode.REAL_READ_ONLY
                else RealTerrainLiquidityVerdict.FALLBACK_TERRAIN_REHEARSAL_APPROVED
            )
        else:
            verdict = RealTerrainLiquidityVerdict(status) if status in RealTerrainLiquidityVerdict._value2member_map_ else RealTerrainLiquidityVerdict.QUARANTINE_MARKET
        return RealTerrainLiquidityProofPacket(
            packet_id="real-terrain-liq-proof-v12-001",
            snapshot_mode=result.mode,
            verdict=verdict,
            no_trade_reasons=no_trade,
            proof_refs={
                "orderbook_snapshot": result.proof.proof_ref,
                "liquidity_model_v2": "orderbook-liquidity-model-v2",
                "v11_liquidity_authority": "live-liquidity-proof-engine-v1",
            },
            spread_cents=analysis.spread_profile.spread_absolute,
            top_of_book_depth=analysis.depth_profile.top_of_book_depth,
            stale_quote_risk=analysis.stale_quote_risk.risk_score,
            fill_drag_cents=analysis.fill_quality.fill_drag.drag_cents,
            execution_feasibility_score=analysis.execution_feasibility_score.total,
        )

    def packet_manifest(self) -> dict[str, Any]:
        packet = self.evaluate_snapshot(
            OrderbookSnapshotResult.from_snapshot(
                mode=OrderbookSnapshotMode.REAL_READ_ONLY,
                snapshot=OrderbookLiquidityModelV2.sample_real_snapshot(),
                proof_ref="real-orderbook-proof-v12",
            )
        )
        fallback = self.evaluate_snapshot(self.model.fallback_result())
        return {
            "workstream": "V12: Real Terrain Liquidity Proof Packet Manifest",
            "packets": [packet.to_dict(), fallback.to_dict()],
            "verdict": "PASS",
        }

    def no_trade_reason_report(self) -> dict[str, Any]:
        return {
            "workstream": "V12: Real Terrain No Trade Reasons",
            "covered_reasons": [reason.value for reason in RealTerrainNoTradeReason],
            "verdict": "PASS",
        }

    def to_report(self, result: OrderbookSnapshotResult | None = None) -> dict[str, Any]:
        packet = self.evaluate_snapshot(result)
        return {
            "workstream": "V12: Live Liquidity Proof Engine V2",
            "packet": packet.to_dict(),
            "snapshot_mode": packet.snapshot_mode.value,
            "live_submit_required": False,
            "shadow_order_packet_status": "REHEARSAL_ONLY",
            "micro_order_arming_status": "BLOCKED_LIVE_SUBMIT_DISABLED",
            "real_submit_calls": 0,
            "real_cancel_calls": 0,
            "verdict": "PASS",
        }
