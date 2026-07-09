from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.registry import get_repo_derived_strategies


@dataclass
class StrategyScanResult:
    family: str
    market_ticker: str
    contract_ticker: str
    edge_estimate: float
    confidence: float
    liquidity_score: float
    spread_score: float
    settlement_risk_score: float
    proposal: Optional[TradeProposal] = None
    no_trade_reason: Optional[str] = None
    critique: Optional[Any] = None
    raw_notes: dict[str, Any] = field(default_factory=dict)


class StrategyScanner:
    """Run repo-derived strategy families against a normalized market snapshot."""

    def __init__(self, strategies: Optional[list] = None):
        self.strategies = strategies if strategies is not None else get_repo_derived_strategies()

    def _extract_scores(self, proposal: TradeProposal | None, forecast: Forecast) -> dict[str, float]:
        if proposal is None:
            return {
                "edge_estimate": 0.0,
                "confidence": float(forecast.confidence_score),
                "liquidity_score": float(forecast.liquidity_score),
                "spread_score": float(forecast.spread_score),
                "settlement_risk_score": float(forecast.settlement_risk_score),
            }
        edge = proposal.edge_estimate.expected_edge_bps / 10000.0 if proposal.edge_estimate else 0.0
        return {
            "edge_estimate": edge,
            "confidence": float(proposal.confidence_estimate),
            "liquidity_score": float(proposal.cap_impact.get("liquidity_score", 0.5)),
            "spread_score": float(proposal.cap_impact.get("spread_score", 0.5)),
            "settlement_risk_score": float(proposal.cap_impact.get("settlement_risk_score", 0.5)),
        }

    def scan(self, forecast: Forecast, orderbook: OrderBook) -> list[StrategyScanResult]:
        results: list[StrategyScanResult] = []
        for strategy in self.strategies:
            try:
                proposal = strategy.evaluate(forecast, orderbook)
            except Exception as exc:
                proposal = None
                no_trade_reason = f"exception: {type(exc).__name__}: {exc}"
            else:
                no_trade_reason = None if proposal is not None else "no edge or below thresholds"

            scores = self._extract_scores(proposal, forecast)
            results.append(
                StrategyScanResult(
                    family=strategy.name,
                    market_ticker=forecast.market_ticker,
                    contract_ticker=forecast.contract_ticker,
                    edge_estimate=scores["edge_estimate"],
                    confidence=scores["confidence"],
                    liquidity_score=scores["liquidity_score"],
                    spread_score=scores["spread_score"],
                    settlement_risk_score=scores["settlement_risk_score"],
                    proposal=proposal,
                    no_trade_reason=no_trade_reason,
                )
            )
        return results
