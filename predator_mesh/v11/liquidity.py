"""Live-liquidity execution proof layer for V11.

The layer is rehearsal-only: it transforms an edge candidate into a bounded
liquidity proof packet, but it never submits or cancels real orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LiquidityProofVerdict(str, Enum):
    LIQUIDITY_REHEARSAL_APPROVED = "LIQUIDITY_REHEARSAL_APPROVED"
    NO_TRADE_LIQUIDITY_TOO_THIN = "NO_TRADE_LIQUIDITY_TOO_THIN"
    NO_TRADE_SPREAD_TOO_WIDE = "NO_TRADE_SPREAD_TOO_WIDE"
    NO_TRADE_STALE_ORDERBOOK = "NO_TRADE_STALE_ORDERBOOK"
    NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG = "NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    REQUIRE_MINIMAX_REVIEW = "REQUIRE_MINIMAX_REVIEW"
    REQUIRE_OPERATOR_REVIEW = "REQUIRE_OPERATOR_REVIEW"
    QUARANTINE_MARKET = "QUARANTINE_MARKET"


class LiquidityProofReason(str, Enum):
    LIQUIDITY_OK = "liquidity_ok"
    LIQUIDITY_TOO_THIN = "liquidity_too_thin"
    SPREAD_TOO_WIDE = "spread_too_wide"
    STALE_ORDERBOOK = "stale_orderbook"
    EDGE_TOO_SMALL_AFTER_FILL_DRAG = "edge_too_small_after_fill_drag"
    HIGH_DISAGREEMENT = "high_disagreement"
    HIGH_SETTLEMENT_RISK = "high_settlement_risk"
    MISSING_PROOF = "missing_proof"
    QUARANTINE_MARKET = "quarantine_market"


@dataclass(frozen=True)
class LiquidityExecutionTerrain:
    spread_score: float
    depth_score: float
    liquidity_score: float
    freshness_score: float
    settlement_risk_score: float
    fill_drag: float
    limit_order_only: bool = True
    market_orders_allowed: bool = False
    max_timeout_s: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "spread_score": self.spread_score,
            "depth_score": self.depth_score,
            "liquidity_score": self.liquidity_score,
            "freshness_score": self.freshness_score,
            "settlement_risk_score": self.settlement_risk_score,
            "fill_drag": self.fill_drag,
            "limit_order_only": self.limit_order_only,
            "market_orders_allowed": self.market_orders_allowed,
            "max_timeout_s": self.max_timeout_s,
        }


@dataclass(frozen=True)
class LiquidityAttackReadiness:
    ready_for_shadow_order: bool
    readiness_score: float
    no_trade_pressure: float
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready_for_shadow_order": self.ready_for_shadow_order,
            "readiness_score": self.readiness_score,
            "no_trade_pressure": self.no_trade_pressure,
            "action": self.action,
        }


@dataclass(frozen=True)
class LiquidityOpportunity:
    edge_candidate_id: str
    forecast_ref: str
    strategy_governor_ref: str
    market_ticker: str
    contract_ticker: str
    expected_edge: float
    terrain: LiquidityExecutionTerrain
    cap_impact: dict[str, Any]
    model_agreement: float
    model_disagreement: float
    calibration_support: float
    no_trade_pressure: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_candidate_id": self.edge_candidate_id,
            "forecast_ref": self.forecast_ref,
            "strategy_governor_ref": self.strategy_governor_ref,
            "market_ticker": self.market_ticker,
            "contract_ticker": self.contract_ticker,
            "expected_edge": self.expected_edge,
            "execution_terrain": self.terrain.to_dict(),
            "cap_impact": self.cap_impact,
            "model_agreement": self.model_agreement,
            "model_disagreement": self.model_disagreement,
            "calibration_support": self.calibration_support,
            "no_trade_pressure": self.no_trade_pressure,
        }


@dataclass(frozen=True)
class LiquidityProofPacket:
    packet_id: str
    opportunity: LiquidityOpportunity
    verdict: LiquidityProofVerdict
    reasons: list[str]
    attack_readiness: LiquidityAttackReadiness
    proof_refs: dict[str, str]
    live_submit_required: bool = False
    firewall_rehearsal_status: str = "BLOCKED_LIVE_SUBMIT_DISABLED"

    @property
    def execution_terrain(self) -> LiquidityExecutionTerrain:
        return self.opportunity.terrain

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "market_ticker": self.opportunity.market_ticker,
            "contract_ticker": self.opportunity.contract_ticker,
            "verdict": self.verdict.value,
            "reasons": self.reasons,
            "execution_terrain": self.execution_terrain.to_dict(),
            "attack_readiness": self.attack_readiness.to_dict(),
            "proof_refs": self.proof_refs,
            "live_submit_required": self.live_submit_required,
            "firewall_rehearsal_status": self.firewall_rehearsal_status,
        }


class LiveLiquidityProofEngine:
    LIQUIDITY_MIN = 0.30
    SPREAD_MIN = 0.30
    FRESHNESS_MIN = 0.30
    SETTLEMENT_REVIEW = 0.70
    SETTLEMENT_QUARANTINE = 0.90
    DISAGREEMENT_REVIEW = 0.35

    @staticmethod
    def sample_opportunity(
        *,
        liquidity_score: float = 0.82,
        spread_score: float = 0.78,
        depth_score: float = 0.74,
        freshness_score: float = 0.92,
        fill_drag: float = 0.05,
        expected_edge: float = 0.18,
        settlement_risk_score: float = 0.18,
        model_disagreement: float = 0.12,
    ) -> LiquidityOpportunity:
        return LiquidityOpportunity(
            edge_candidate_id="edge-v11-001",
            forecast_ref="forecast-proof-v11-001",
            strategy_governor_ref="strategy-governor-proof-v11-001",
            market_ticker="KXDEMO-LIQUIDITY",
            contract_ticker="KXDEMO-LIQUIDITY-YES",
            expected_edge=expected_edge,
            terrain=LiquidityExecutionTerrain(
                spread_score=spread_score,
                depth_score=depth_score,
                liquidity_score=liquidity_score,
                freshness_score=freshness_score,
                settlement_risk_score=settlement_risk_score,
                fill_drag=fill_drag,
            ),
            cap_impact={"would_breach_single_order": False, "would_breach_market": False},
            model_agreement=max(0.0, 1.0 - model_disagreement),
            model_disagreement=model_disagreement,
            calibration_support=0.72,
            no_trade_pressure=0.18,
        )

    def evaluate(self, opportunity: LiquidityOpportunity) -> LiquidityProofPacket:
        terrain = opportunity.terrain
        edge_after_drag = opportunity.expected_edge - terrain.fill_drag
        verdict = LiquidityProofVerdict.LIQUIDITY_REHEARSAL_APPROVED
        reasons = [LiquidityProofReason.LIQUIDITY_OK.value]

        if not opportunity.forecast_ref or not opportunity.strategy_governor_ref:
            verdict = LiquidityProofVerdict.REQUIRE_MORE_EVIDENCE
            reasons = [LiquidityProofReason.MISSING_PROOF.value]
        elif terrain.liquidity_score < self.LIQUIDITY_MIN or terrain.depth_score < self.LIQUIDITY_MIN:
            verdict = LiquidityProofVerdict.NO_TRADE_LIQUIDITY_TOO_THIN
            reasons = [LiquidityProofReason.LIQUIDITY_TOO_THIN.value]
        elif terrain.spread_score < self.SPREAD_MIN:
            verdict = LiquidityProofVerdict.NO_TRADE_SPREAD_TOO_WIDE
            reasons = [LiquidityProofReason.SPREAD_TOO_WIDE.value]
        elif terrain.freshness_score < self.FRESHNESS_MIN:
            verdict = LiquidityProofVerdict.NO_TRADE_STALE_ORDERBOOK
            reasons = [LiquidityProofReason.STALE_ORDERBOOK.value]
        elif edge_after_drag <= 0:
            verdict = LiquidityProofVerdict.NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG
            reasons = [LiquidityProofReason.EDGE_TOO_SMALL_AFTER_FILL_DRAG.value]
        elif terrain.settlement_risk_score >= self.SETTLEMENT_QUARANTINE:
            verdict = LiquidityProofVerdict.QUARANTINE_MARKET
            reasons = [LiquidityProofReason.QUARANTINE_MARKET.value]
        elif terrain.settlement_risk_score >= self.SETTLEMENT_REVIEW:
            verdict = LiquidityProofVerdict.REQUIRE_OPERATOR_REVIEW
            reasons = [LiquidityProofReason.HIGH_SETTLEMENT_RISK.value]
        elif opportunity.model_disagreement >= self.DISAGREEMENT_REVIEW:
            verdict = LiquidityProofVerdict.REQUIRE_MINIMAX_REVIEW
            reasons = [LiquidityProofReason.HIGH_DISAGREEMENT.value]

        ready = verdict is LiquidityProofVerdict.LIQUIDITY_REHEARSAL_APPROVED
        readiness_score = round(
            max(
                0.0,
                min(
                    1.0,
                    terrain.liquidity_score * 0.25
                    + terrain.spread_score * 0.20
                    + terrain.depth_score * 0.20
                    + terrain.freshness_score * 0.15
                    + opportunity.calibration_support * 0.10
                    + max(0.0, edge_after_drag) * 0.10
                    - opportunity.no_trade_pressure * 0.10,
                ),
            ),
            4,
        )
        packet = LiquidityProofPacket(
            packet_id=f"liq-proof-{opportunity.edge_candidate_id}",
            opportunity=opportunity,
            verdict=verdict,
            reasons=reasons,
            attack_readiness=LiquidityAttackReadiness(
                ready_for_shadow_order=ready,
                readiness_score=readiness_score,
                no_trade_pressure=opportunity.no_trade_pressure,
                action="ESCALATE_TO_SHADOW_ORDER" if ready else "NO_TRADE_OR_REVIEW",
            ),
            proof_refs={
                "edge_candidate": opportunity.edge_candidate_id,
                "forecast_opinion": opportunity.forecast_ref,
                "strategy_governor": opportunity.strategy_governor_ref,
                "liquidity_proof": f"proof-{opportunity.edge_candidate_id}",
            },
        )
        return packet

    def packet_manifest(self) -> dict[str, Any]:
        packets = [
            self.evaluate(self.sample_opportunity()),
            self.evaluate(self.sample_opportunity(liquidity_score=0.10)),
            self.evaluate(self.sample_opportunity(spread_score=0.10)),
            self.evaluate(self.sample_opportunity(freshness_score=0.10)),
        ]
        return {
            "workstream": "V11: Liquidity Proof Packet Manifest",
            "packets": [packet.to_dict() for packet in packets],
            "verdict": "PASS" if packets else "FAIL",
        }

    def to_report(self) -> dict[str, Any]:
        manifest = self.packet_manifest()
        approved = [p for p in manifest["packets"] if p["verdict"] == LiquidityProofVerdict.LIQUIDITY_REHEARSAL_APPROVED.value]
        return {
            "workstream": "V11: Live Liquidity Proof Engine",
            "packet_count": len(manifest["packets"]),
            "approved_rehearsal_count": len(approved),
            "live_submit_required": False,
            "limit_order_only": True,
            "firewall_rehearsal_status": "BLOCKED_LIVE_SUBMIT_DISABLED",
            "packets": manifest["packets"],
            "verdict": "PASS" if approved else "FAIL",
        }
