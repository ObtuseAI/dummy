"""Calibration-weighted ensemble forecaster.

Fuses per-source signals by inverse-variance weighting scaled by each
source's ledger trust weight. A source only gains influence by having been
right, in this vertical, in the past — the mechanical heart of "self-
learning".
"""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Forecast, MarketView, Signal


class EnsembleForecaster:
    def __init__(self, ledger: AutonomyLedger):
        self.ledger = ledger

    def fuse(self, market: MarketView, signals: list[Signal]) -> Forecast | None:
        if not signals:
            return None
        weighted: dict[str, float] = {}
        numerator = 0.0
        denominator = 0.0
        for signal in signals:
            # Vertical-scoped trust when the ledger has earned one; a source's
            # authority is domain-specific, not global. Duck-typed fallback
            # keeps minimal ledger stand-ins working.
            scoped = getattr(self.ledger, "get_weight_scoped", None)
            if callable(scoped):
                trust = scoped(signal.source, market.vertical.value)
            else:
                trust = self.ledger.get_weight(signal.source, default=1.0)
            variance = max(1e-4, signal.uncertainty**2)
            weight = trust / variance
            weighted[signal.source] = weight
            numerator += weight * signal.probability_yes
            denominator += weight
        if denominator <= 0:
            return None
        probability = min(0.995, max(0.005, numerator / denominator))
        # Fused uncertainty: inverse of total precision, floored so a single
        # confident source can never claim certainty.
        fused_sigma = max(0.02, (1.0 / denominator) ** 0.5)

        implied = None
        if market.yes_bid is not None and market.yes_ask is not None and market.yes_ask > 0:
            implied = ((market.yes_bid + market.yes_ask) / 2.0) / 100.0
        edge = probability - implied if implied is not None else 0.0

        total = sum(weighted.values())
        normalized = {source: round(w / total, 4) for source, w in weighted.items()} if total else {}
        rationale = "; ".join(
            f"{s.source}:{s.probability_yes:.2f}±{s.uncertainty:.2f}" for s in signals
        )
        return Forecast(
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=fused_sigma,
            sources_used=normalized,
            market_implied_yes=implied,
            edge_yes=edge,
            rationale=rationale[:600],
        )
