"""Crypto specialist -- Phase 0 wrapper.

Routes BTC/ETH/SOL contracts and exposes the champion lognormal view behind
the council protocol. ``book()`` abstains in Phase 0; Phase 1 fills it with
the Deribit DVOL implied-volatility book (risk-neutral P(above strike) from
implied rather than realized sigma) so crypto gains the same model-vs-book
triangulation MLB already has.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.specialists.base import SpecialistHealth


class CryptoSpecialist:
    """Crypto council member wrapping the registered champion signal."""

    name = "crypto"

    def __init__(self, champion: Any) -> None:
        # ``champion`` is the registered CryptoSpotVolSignal instance
        # (shared per-cycle spot/vol cache); never constructed here.
        self.champion = champion

    def applicable(self, market: MarketView) -> bool:
        from autonomy.signals.crypto_spot import parse_crypto_ticker

        return (
            market.vertical is Vertical.CRYPTO
            and parse_crypto_ticker(market.ticker) is not None
        )

    def forecast(self, market: MarketView) -> Signal | None:
        if self.champion is None or not self.applicable(market):
            return None
        try:
            return self.champion.generate(market)
        except Exception:
            return None

    def live_forecast(self, market: MarketView) -> Signal | None:
        # Crypto contracts are continuously repriced by the champion model;
        # there is no separate in-play phase. Abstain.
        return None

    def book(self, market: MarketView) -> float | None:
        # Phase 1: Deribit DVOL implied book. Until then, no crypto book --
        # assessments stay "model_only", byte-identical to pre-council runs.
        return None

    def on_cycle_start(self) -> None:
        # The shared CryptoDataHub is warmed by the brain's registry cycle.
        return None

    def health(self) -> SpecialistHealth:
        return SpecialistHealth(
            name=self.name,
            status="ok" if self.champion is not None else "cold",
            details={"has_champion": self.champion is not None, "book": "phase-1"},
        )
