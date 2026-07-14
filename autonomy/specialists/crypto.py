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

    def __init__(self, champion: Any, implied_book: Any = None) -> None:
        # ``champion`` is the registered CryptoSpotVolSignal instance
        # (shared per-cycle spot/vol cache); never constructed here.
        # ``implied_book`` is the Deribit DVOL CryptoImpliedBook (Phase 1);
        # None keeps the Phase 0 behavior (book abstains, model_only).
        self.champion = champion
        self.implied_book = implied_book

    def applicable(self, market: MarketView) -> bool:
        from autonomy.signals.crypto_spot import parse_crypto_ticker

        return (
            market.vertical is Vertical.CRYPTO
            and parse_crypto_ticker(market.ticker) is not None
        )

    def forecast(self, market: MarketView) -> Signal | None:
        try:
            if self.champion is None or not self.applicable(market):
                return None
            return self.champion.generate(market)
        except Exception:
            return None

    def live_forecast(self, market: MarketView) -> Signal | None:
        # Crypto contracts are continuously repriced by the champion model;
        # there is no separate in-play phase. Abstain.
        return None

    def book(self, market: MarketView) -> float | None:
        # Deribit DVOL implied book: risk-neutral P(above strike) from
        # forward-looking implied sigma -- the independent counterpart to the
        # champion's realized sigma. No book wired (or no DVOL/state) means
        # abstain and assessments stay "model_only".
        try:
            if self.implied_book is None or not self.applicable(market):
                return None
            return self.implied_book.book_probability(market)
        except Exception:
            return None

    def ejection_events(self, market: MarketView) -> tuple[dict[str, Any], ...]:
        return ()

    def on_cycle_start(self) -> None:
        # The shared CryptoDataHub is warmed by the brain's registry cycle.
        return None

    def health(self) -> SpecialistHealth:
        return SpecialistHealth(
            name=self.name,
            status="ok" if self.champion is not None else "cold",
            details={
                "has_champion": self.champion is not None,
                "book": "dvol_implied" if self.implied_book is not None else "none",
            },
        )
