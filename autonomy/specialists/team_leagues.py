"""Team-league specialists (NBA/NFL/NCAAF/NHL/NCAAMB) -- Phase 0 wrappers.

Each league gets its own council member so later phases can deepen one league
without touching the others (NFL key-number margins, NBA pace-and-efficiency,
NHL goalie identity...). Phase 0 wraps the shipped generic
``TeamSportsIntelligenceSignal`` view and the sportsbook-consensus book with
zero behavior change.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.specialists.base import SpecialistHealth


class TeamLeagueSpecialist:
    """One pro/college team league wrapped behind the specialist protocol."""

    def __init__(self, league: str, intelligence: Any, sportsbook: Any) -> None:
        self.name = league
        self.league = league
        self.intelligence = intelligence
        self.sportsbook = sportsbook

    def _parsed(self, market: MarketView):
        from autonomy.signals.sports_intelligence import parse_sports_contract

        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != self.league:
            return None
        return parsed

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._parsed(market) is not None

    def forecast(self, market: MarketView) -> Signal | None:
        if self.intelligence is None or not self.applicable(market):
            return None
        try:
            return self.intelligence.generate(market)
        except Exception:
            return None

    def live_forecast(self, market: MarketView) -> Signal | None:
        # No live in-play model for this league yet (Phases 3-5); abstain so
        # callers keep their pre-council behavior.
        return None

    def book(self, market: MarketView) -> float | None:
        try:
            if self.sportsbook is not None and self.sportsbook.applicable(market):
                signal = self.sportsbook.generate(market)
                return signal.probability_yes if signal else None
            return None
        except Exception:
            return None

    def on_cycle_start(self) -> None:
        # Shared signal instances are warmed by the brain's registry cycle.
        return None

    def health(self) -> SpecialistHealth:
        details: dict[str, Any] = {
            "has_intelligence": self.intelligence is not None,
            "has_sportsbook": self.sportsbook is not None,
        }
        models = getattr(self.intelligence, "models", None)
        if isinstance(models, dict) and self.league in models:
            details["score_games_seen"] = getattr(models[self.league], "games_seen", None)
        status = "ok" if self.intelligence is not None else "cold"
        return SpecialistHealth(name=self.name, status=status, details=details)
