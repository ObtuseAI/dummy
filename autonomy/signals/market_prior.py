"""Market-prior signal: the book's own mid as a Bayesian anchor.

Prediction markets are usually right. Fusing the market's implied probability
as one weighted voice regularizes the ensemble against model overconfidence —
edge then requires *disagreeing with the market for a reason the calibration
ledger has historically rewarded*. Weight decays with book thinness: an empty
book earns almost no anchoring power.
"""
from __future__ import annotations

from autonomy.ontology import MarketView, Signal


class MarketPriorSignal:
    name = "market_prior"

    def applicable(self, market: MarketView) -> bool:
        return market.yes_bid is not None and market.yes_ask is not None and market.yes_ask > 0

    def generate(self, market: MarketView) -> Signal | None:
        if market.yes_bid is None or market.yes_ask is None:
            return None
        mid = (market.yes_bid + market.yes_ask) / 2.0
        spread = market.yes_ask - market.yes_bid
        # Thin/wide books are weak anchors; encode that in the uncertainty.
        thinness = 0.0 if market.volume >= 1000 else (0.15 if market.volume >= 100 else 0.3)
        uncertainty = min(0.5, spread / 100.0 + thinness)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, mid / 100.0)),
            uncertainty=max(0.02, uncertainty),
            rationale=f"book mid {mid:.1f}c spread {spread}c volume {market.volume}",
            features={"mid": mid, "spread": spread, "volume": market.volume},
        )
