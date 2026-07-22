from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.ontology import Forecast, OrderBook, TradeProposal
from autonomy.target_policy import is_prediction_quarantined_target
from strategies.registry import get_repo_derived_strategies, has_prediction_authority


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
    """Run prediction-authorized strategy families against a market snapshot.

    Data-only and explicitly no-authority strategies are excluded even when a
    legacy caller injects them directly. They therefore produce neither scan
    rows nor trade proposals.
    """

    def __init__(self, strategies: Optional[list] = None):
        candidates = strategies if strategies is not None else get_repo_derived_strategies()
        self.strategies = [
            strategy for strategy in candidates if has_prediction_authority(strategy)
        ]

    def _active_strategies(self) -> tuple[Any, ...]:
        """Reapply the authority filter in case a legacy caller mutates the list."""
        return tuple(
            strategy
            for strategy in self.strategies
            if has_prediction_authority(strategy)
        )

    @property
    def active_family_names(self) -> tuple[str, ...]:
        """Ordered names of the families this scanner is allowed to evaluate."""
        return tuple(str(strategy.name) for strategy in self._active_strategies())

    @property
    def active_family_count(self) -> int:
        """Number of prediction-authorized families in this scanner."""
        return len(self.active_family_names)

    def family_has_prediction_authority(self, family: str) -> bool:
        """Bind a scan family to exactly one explicitly-authorized strategy."""
        matches = [
            strategy
            for strategy in self._active_strategies()
            if str(getattr(strategy, "name", "")) == str(family)
        ]
        return len(matches) == 1 and has_prediction_authority(matches[0])

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

    def scan(
        self,
        forecast: Forecast,
        orderbook: OrderBook,
        *,
        market_category: str | None = None,
    ) -> list[StrategyScanResult]:
        # Repositories and injected strategy objects are untrusted proposal
        # producers.  Apply the shared target gate before calling any strategy;
        # caller-authored private fields cannot bypass it.
        if is_prediction_quarantined_target(
            forecast.market_ticker,
            category=market_category,
        ) or is_prediction_quarantined_target(
            forecast.contract_ticker,
            category=market_category,
        ):
            return []
        results: list[StrategyScanResult] = []
        for strategy in self._active_strategies():
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
