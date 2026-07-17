"""Market-prior signal: the book's own mid as a Bayesian anchor.

Prediction markets are usually right. Fusing the market's implied probability
as one weighted voice regularizes the ensemble against model overconfidence —
edge then requires *disagreeing with the market for a reason the calibration
ledger has historically rewarded*.

This signal is also the GRADING BENCHMARK: the learner, backtest, and miner
all score every source against the market_prior emission. A dead or wide book
must therefore produce NO emission at all (Wave-5 honest-quote gate): a
fabricated ~50c mid on an unquoted strike is not a market opinion, and
"beating" it was the audit's largest evidence contamination. No honest quote
→ abstain, so junk books yield no anchor, no benchmark, and no trust movement.
"""
from __future__ import annotations

from autonomy.ontology import MarketView, Signal
from autonomy.quote_quality import honest_implied_yes


class MarketPriorSignal:
    name = "market_prior"

    def applicable(self, market: MarketView) -> bool:
        return honest_implied_yes(market.yes_bid, market.yes_ask) is not None

    def generate(self, market: MarketView) -> Signal | None:
        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        if implied is None:
            return None
        mid = (market.yes_bid + market.yes_ask) / 2.0
        spread = market.yes_ask - market.yes_bid
        # Thin books are weak anchors; encode that in the uncertainty.
        thinness = 0.0 if market.volume >= 1000 else (0.15 if market.volume >= 100 else 0.3)
        uncertainty = min(0.5, spread / 100.0 + thinness)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, implied)),
            uncertainty=max(0.02, uncertainty),
            rationale=f"book mid {mid:.1f}c spread {spread}c volume {market.volume}",
            features={"mid": mid, "spread": spread, "volume": market.volume},
        )
