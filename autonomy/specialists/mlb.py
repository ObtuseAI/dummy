"""MLB specialist: wraps the shipped MLB intelligence stack (Phase 0).

Owns exactly the MLB-specific wiring the mispricing monitor previously
hand-built in its ``_build()`` closures: routing MLB contracts, the live
challenger view for in-progress games, and the sharp book (live ESPN-summary
de-vig when in play, pre-game sportsbook consensus otherwise). Behavior is
byte-identical to the pre-council monitor by construction.
"""
from __future__ import annotations

from typing import Any

from autonomy.live_odds import EspnSummaryBook
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.specialists.base import SpecialistHealth
from autonomy.sports.espn import EspnClient, canonical_team


class MlbSpecialist:
    """MLB council member wrapping the shipped signal instances."""

    name = "mlb"

    def __init__(
        self,
        intelligence: Any,
        sportsbook: Any,
        espn: EspnClient | None = None,
        live_book: EspnSummaryBook | None = None,
    ) -> None:
        # ``intelligence`` is the registered BaseballIntelligenceSignal
        # instance (shared model state); ``sportsbook`` the registered
        # SportsbookConsensusSignal. Passed in -- never constructed here --
        # so the specialist shares the brain's live state and caches.
        self.intelligence = intelligence
        self.sportsbook = sportsbook
        self.espn = espn or EspnClient()
        self.live_book = live_book or EspnSummaryBook(league="mlb")

    # -- routing ---------------------------------------------------------
    def _parsed(self, market: MarketView):
        from autonomy.signals.sports_intelligence import parse_sports_contract

        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != "mlb":
            return None
        return parsed

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._parsed(market) is not None

    def _live_game(self, market: MarketView):
        """Resolve an in-progress MLB game for a winner market, else None."""
        parsed = self._parsed(market)
        if parsed is None or parsed.market_type != "winner" or not parsed.competitors:
            return None
        game = self.espn.find_matchup(
            "mlb", parsed.competitors[0], parsed.competitors[1], parsed.date_yyyymmdd)
        if game is None or game.status != "in":
            return None
        return parsed, game

    # -- protocol --------------------------------------------------------
    def forecast(self, market: MarketView) -> Signal | None:
        try:
            if self.intelligence is None or not self.applicable(market):
                return None
            return self.intelligence.generate(market)
        except Exception:
            return None

    def live_forecast(self, market: MarketView) -> Signal | None:
        try:
            if self.intelligence is None or self._live_game(market) is None:
                return None
            signal = self.intelligence.generate(market)
            if signal is not None and signal.features.get("live"):
                return signal
            return None
        except Exception:
            return None

    def book(self, market: MarketView) -> float | None:
        try:
            resolved = self._live_game(market)
            if resolved is not None:
                parsed, game = resolved
                home_prob = self.live_book.home_win_probability(game.game_id)
                if home_prob is not None:
                    subject = canonical_team("mlb", parsed.subject or "")
                    yes_is_home = subject == canonical_team("mlb", game.home)
                    return home_prob if yes_is_home else 1.0 - home_prob
            if self.sportsbook is not None and self.sportsbook.applicable(market):
                signal = self.sportsbook.generate(market)
                return signal.probability_yes if signal else None
            return None
        except Exception:
            return None

    def on_cycle_start(self) -> None:
        # Shared signal instances are warmed by the brain's own registry
        # cycle; the specialist only clears its private live-book cache so a
        # new pass re-reads in-play odds.
        self.live_book.clear()

    def health(self) -> SpecialistHealth:
        details: dict[str, Any] = {
            "has_intelligence": self.intelligence is not None,
            "has_sportsbook": self.sportsbook is not None,
        }
        model = getattr(self.intelligence, "model", None)
        if model is not None:
            details["games_seen"] = getattr(model, "games_seen", None)
        status = "ok" if self.intelligence is not None else "cold"
        return SpecialistHealth(name=self.name, status=status, details=details)
